import stripe
from sqlalchemy.orm import Session
from app.models.idempotency import IdempotencyKey
from app.repositories.payment_repository import payment as payment_repo
from app.repositories.order_repository import order as order_repo
from app.models.subscription import Subscription
from app.models.customer import Customer
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# CHECKOUT SESSION HANDLERS
# ============================================================================

def handle_checkout_session_completed(db: Session, event: stripe.Event):
    """Handle completed checkout session - link payment_intent to payment record and verify capture"""
    session = event.data.object
    checkout_session_id = session.id
    payment_intent_id = session.payment_intent if session.mode == 'payment' else None
    subscription_id = session.subscription if session.mode == 'subscription' else None
    payment_status = session.payment_status  # 'paid', 'unpaid', or 'no_payment_required'
    
    # Handle payment mode checkout
    if session.mode == 'payment' and payment_intent_id:
        db_payment = payment_repo.get_by_checkout_session(db, checkout_session_id)
        
        if db_payment:
            # Update payment with payment_intent_id
            payment_repo.update(db, db_obj=db_payment, obj_in={
                "stripe_payment_intent_id": payment_intent_id
            })
            logger.info(
                f"Linked Payment {db_payment.id} to PaymentIntent {payment_intent_id}. "
                f"Payment status: {payment_status}"
            )
            
            # Verify the PaymentIntent is captured
            try:
                payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                logger.info(
                    f"PaymentIntent {payment_intent_id} status: {payment_intent.status}, "
                    f"capture_method: {payment_intent.capture_method}, "
                    f"amount_captured: {payment_intent.amount_captured}"
                )
                
                # If payment is authorized but not captured, capture it now
                if payment_intent.status == 'requires_capture':
                    logger.warning(f"PaymentIntent {payment_intent_id} requires manual capture. Capturing now...")
                    captured_intent = stripe.PaymentIntent.capture(payment_intent_id)
                    logger.info(f"PaymentIntent {payment_intent_id} captured successfully. Amount: {captured_intent.amount_captured/100}")
                    
            except stripe.error.StripeError as e:
                logger.error(f"Error checking/capturing PaymentIntent {payment_intent_id}: {str(e)}")
                
        else:
            logger.warning(f"Checkout session {checkout_session_id} completed but no Payment found")
    
    # Handle subscription mode checkout
    elif session.mode == 'subscription' and subscription_id:
        # Find subscription by client_reference_id if set
        client_reference_id = session.client_reference_id
        
        if client_reference_id:
            db_sub = db.query(Subscription).filter(Subscription.id == int(client_reference_id)).first()
            if db_sub and not db_sub.stripe_subscription_id:
                db_sub.stripe_subscription_id = subscription_id
                db.commit()
                logger.info(f"Linked Subscription {db_sub.id} to Stripe subscription {subscription_id}")
        else:
            logger.info(f"Subscription checkout completed: {subscription_id}")
    
    else:
        logger.info(f"Checkout session {checkout_session_id} completed in {session.mode} mode")

# ============================================================================
# CUSTOMER HANDLERS
# ============================================================================

def handle_customer_created(db: Session, event: stripe.Event):
    """Handle new customer created in Stripe - sync to local Customer table"""
    stripe_customer = event.data.object

    # Check if already synced
    db_customer = db.query(Customer).filter(
        Customer.stripe_customer_id == stripe_customer.id
    ).first()

    if db_customer:
        logger.info(f"Customer {stripe_customer.id} already exists locally (id={db_customer.id}). Skipping.")
        return

    # Also try to find by email to avoid duplicates
    if stripe_customer.email:
        db_customer = db.query(Customer).filter(
            Customer.email == stripe_customer.email
        ).first()

    if db_customer:
        # Link existing local customer to Stripe customer
        if not db_customer.stripe_customer_id:
            db_customer.stripe_customer_id = stripe_customer.id
            db.commit()
            logger.info(
                f"Linked existing Customer {db_customer.id} ({db_customer.email}) "
                f"to Stripe customer {stripe_customer.id}"
            )
        else:
            logger.warning(
                f"Customer with email {stripe_customer.email} already linked to a "
                f"different Stripe customer ({db_customer.stripe_customer_id}). Skipping."
            )
        return

    # Create new local customer record
    new_customer = Customer(
        email=stripe_customer.email or f"{stripe_customer.id}@unknown.stripe",
        name=stripe_customer.name,
        stripe_customer_id=stripe_customer.id,
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    logger.info(f"Customer {new_customer.id} created from Stripe customer {stripe_customer.id}.")


# ============================================================================
# PAYMENT INTENT HANDLERS
# ============================================================================

def handle_payment_intent_succeeded(db: Session, event: stripe.Event):
    """Handle successful payment intent"""
    intent = event.data.object
    payment_intent_id = intent.id
    
    db_payment = payment_repo.get_by_payment_intent(db, payment_intent_id)
    if db_payment:
        payment_repo.update(db, db_obj=db_payment, obj_in={"status": "succeeded"})
        # Update related order
        db_order = order_repo.get(db, db_payment.order_id)
        if db_order:
            order_repo.update(db, db_obj=db_order, obj_in={"status": "paid"})
        logger.info(f"Payment {db_payment.id} marked as succeeded.")
    else:
        logger.warning(f"PaymentIntent {payment_intent_id} succeeded but no local Payment found.")


def handle_payment_intent_failed(db: Session, event: stripe.Event):
    """Handle failed payment intent"""
    intent = event.data.object
    payment_intent_id = intent.id
    
    db_payment = payment_repo.get_by_payment_intent(db, payment_intent_id)
    if db_payment:
        payment_repo.update(db, db_obj=db_payment, obj_in={"status": "failed"})
        db_order = order_repo.get(db, db_payment.order_id)
        if db_order:
            order_repo.update(db, db_obj=db_order, obj_in={"status": "failed"})
        logger.info(f"Payment {db_payment.id} marked as failed.")
    else:
        logger.warning(f"PaymentIntent {payment_intent_id} failed but no local Payment found.")


def handle_payment_intent_canceled(db: Session, event: stripe.Event):
    """Handle canceled payment intent"""
    intent = event.data.object
    payment_intent_id = intent.id
    
    db_payment = payment_repo.get_by_payment_intent(db, payment_intent_id)
    if db_payment:
        payment_repo.update(db, db_obj=db_payment, obj_in={"status": "canceled"})
        db_order = order_repo.get(db, db_payment.order_id)
        if db_order:
            order_repo.update(db, db_obj=db_order, obj_in={"status": "canceled"})
        logger.info(f"Payment {db_payment.id} marked as canceled.")
    else:
        logger.warning(f"PaymentIntent {payment_intent_id} canceled but no local Payment found.")

# ============================================================================
# SUBSCRIPTION HANDLERS
# ============================================================================

def handle_subscription_created(db: Session, event: stripe.Event):
    """Handle new subscription creation"""
    subscription = event.data.object
    
    # Check if subscription already exists
    db_sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription.id
    ).first()
    
    if db_sub:
        logger.info(f"Subscription {subscription.id} already exists locally.")
        return
    
    # Find customer by stripe_customer_id
    customer = db.query(Customer).filter(
        Customer.stripe_customer_id == subscription.customer
    ).first()
    
    if not customer:
        logger.warning(f"Customer {subscription.customer} not found for subscription {subscription.id}")
        return
    
    # Get the stripe_price_id from subscription
    stripe_price_id = subscription.items.data[0].price.id if subscription.items.data else None
    
    if not stripe_price_id:
        logger.error(f"No price found in subscription {subscription.id}")
        return
    
    # Find the local price by stripe_price_id
    from app.models.product import Price
    local_price = db.query(Price).filter(Price.stripe_price_id == stripe_price_id).first()
    
    if not local_price:
        logger.warning(f"Price {stripe_price_id} not found locally for subscription {subscription.id}. Creating subscription without price_id link.")
        # Create subscription without price_id if not found locally
        price_id = None
    else:
        price_id = local_price.id
    
    # Create new subscription record
    new_sub = Subscription(
        customer_id=customer.id,
        price_id=price_id,  # May be None if price not found locally
        stripe_subscription_id=subscription.id,
        stripe_customer_id=subscription.customer,
        stripe_price_id=stripe_price_id,
        status=subscription.status,
        cancel_at_period_end=subscription.cancel_at_period_end,
        current_period_start=datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc),
        current_period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
        trial_start=datetime.fromtimestamp(subscription.trial_start, tz=timezone.utc) if subscription.trial_start else None,
        trial_end=datetime.fromtimestamp(subscription.trial_end, tz=timezone.utc) if subscription.trial_end else None,
    )
    
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    logger.info(f"Subscription {new_sub.id} created with status {subscription.status}.")


def handle_subscription_updated(db: Session, event: stripe.Event):
    """Handle subscription updates"""
    subscription = event.data.object
    
    db_sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription.id
    ).first()
    
    if db_sub:
        db_sub.status = subscription.status
        db_sub.cancel_at_period_end = subscription.cancel_at_period_end
        
        if getattr(subscription, 'current_period_start', None):
            db_sub.current_period_start = datetime.fromtimestamp(
                subscription.current_period_start, tz=timezone.utc
            )
        
        if getattr(subscription, 'current_period_end', None):
            db_sub.current_period_end = datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            )
        
        if getattr(subscription, 'trial_end', None):
            db_sub.trial_end = datetime.fromtimestamp(
                subscription.trial_end, tz=timezone.utc
            )
        
        db.commit()
        logger.info(f"Subscription {db_sub.id} updated to status {subscription.status}.")
    else:
        logger.warning(f"Subscription {subscription.id} not found for update.")


def handle_subscription_deleted(db: Session, event: stripe.Event):
    """Handle subscription deletion/cancellation"""
    subscription = event.data.object
    
    db_sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription.id
    ).first()
    
    if db_sub:
        db_sub.status = 'canceled'
        db.commit()
        logger.info(f"Subscription {db_sub.id} canceled.")
    else:
        logger.warning(f"Subscription {subscription.id} not found for deletion.")


def handle_subscription_trial_will_end(db: Session, event: stripe.Event):
    """Handle subscription trial ending soon (typically 3 days before)"""
    subscription = event.data.object
    
    db_sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription.id
    ).first()
    
    if db_sub:
        customer = db.query(Customer).filter(Customer.id == db_sub.customer_id).first()
        
        if customer:
            # Log notification - In production, send email/SMS here
            trial_end_date = datetime.fromtimestamp(subscription.trial_end, tz=timezone.utc)
            logger.info(
                f"Trial ending soon for subscription {db_sub.id}. "
                f"Customer: {customer.email}, Trial ends: {trial_end_date}"
            )
            
            # TODO: Integrate with email service (SendGrid, SES, etc.)
            # send_email(
            #     to=customer.email,
            #     subject="Your trial is ending soon",
            #     body=f"Your trial will end on {trial_end_date}"
            # )
        else:
            logger.warning(f"Customer not found for subscription {db_sub.id}")
    else:
        logger.warning(f"Subscription {subscription.id} not found for trial notification.")


# ============================================================================
# CHARGE HANDLERS (Refunds & Disputes)
# ============================================================================

def handle_charge_refunded(db: Session, event: stripe.Event):
    """Handle charge refund"""
    charge = event.data.object
    payment_intent_id = charge.payment_intent
    
    if not payment_intent_id:
        logger.warning(f"Charge {charge.id} refunded but no payment_intent found.")
        return
    
    db_payment = payment_repo.get_by_payment_intent(db, payment_intent_id)
    
    if db_payment:
        # Check if fully or partially refunded (Stripe amounts are in cents)
        amount_refunded_cents = charge.amount_refunded
        total_amount_cents = charge.amount
        
        # Convert cents to dollars
        amount_refunded = amount_refunded_cents / 100
        total_amount = total_amount_cents / 100
        
        if amount_refunded >= total_amount:
            # Fully refunded
            payment_repo.update(db, db_obj=db_payment, obj_in={"status": "refunded"})
            logger.info(f"Payment {db_payment.id} fully refunded. Amount: ${amount_refunded:.2f}")
            
            # Update order status
            db_order = order_repo.get(db, db_payment.order_id)
            if db_order:
                order_repo.update(db, db_obj=db_order, obj_in={"status": "refunded"})
        else:
            # Partially refunded
            payment_repo.update(db, db_obj=db_payment, obj_in={"status": "partially_refunded"})
            logger.info(
                f"Payment {db_payment.id} partially refunded. "
                f"Refunded: ${amount_refunded:.2f}, "
                f"Total: ${total_amount:.2f}"
            )
            
            # Optionally update order to partially_refunded status
            db_order = order_repo.get(db, db_payment.order_id)
            if db_order:
                order_repo.update(db, db_obj=db_order, obj_in={"status": "partially_refunded"})
    else:
        logger.warning(f"Payment for PaymentIntent {payment_intent_id} not found for refund.")


def handle_charge_dispute_created(db: Session, event: stripe.Event):
    """Handle dispute (chargeback) on a charge"""
    dispute = event.data.object
    charge_id = dispute.charge
    payment_intent_id = dispute.payment_intent
    
    if payment_intent_id:
        db_payment = payment_repo.get_by_payment_intent(db, payment_intent_id)
        
        if db_payment:
            # Log dispute information
            logger.warning(
                f"DISPUTE created for Payment {db_payment.id}. "
                f"Reason: {dispute.reason}, Amount: {dispute.amount/100} {dispute.currency.upper()}, "
                f"Status: {dispute.status}"
            )
            
            # You might want to add a dispute status or flag
            # For now, we'll keep the payment status but log it
            # In production, you'd want to:
            # 1. Store dispute details in a separate Dispute table
            # 2. Alert administrators
            # 3. Possibly freeze related services
            
            # TODO: Create Dispute model and store dispute data
            # TODO: Send alert to admin team
            # TODO: Update payment with dispute flag
        else:
            logger.warning(f"Payment for disputed charge {charge_id} not found.")
    else:
        logger.warning(f"Dispute {dispute.id} created but no payment_intent linked.")


# ============================================================================
# INVOICE HELPERS
# ============================================================================

def _get_subscription_id_from_invoice(invoice) -> str | None:
    """
    Extract the Stripe subscription ID from an invoice object.

    Stripe API >= 2026-04-22.dahlia moved `invoice.subscription` into
    `invoice.parent.subscription_details.subscription`.  We support both
    shapes so the code works with old and new API versions.
    """
    # New API shape (2026-04-22.dahlia+)
    try:
        parent = invoice.parent
        if parent and getattr(parent, 'type', None) == 'subscription_details':
            sub_details = getattr(parent, 'subscription_details', None)
            if sub_details:
                return getattr(sub_details, 'subscription', None)
    except Exception:
        pass

    # Legacy / fallback: top-level invoice.subscription
    return getattr(invoice, 'subscription', None)


# ============================================================================
# INVOICE HANDLERS (For Subscriptions)
# ============================================================================

def handle_invoice_payment_succeeded(db: Session, event: stripe.Event):
    """Handle successful invoice payment (for subscriptions)"""
    invoice = event.data.object
    subscription_id = _get_subscription_id_from_invoice(invoice)

    if not subscription_id:
        logger.info(f"Invoice {invoice.id} paid but not related to a subscription.")
        return
    
    try:
        db_sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()
        
        if db_sub:
            # Update subscription status if needed
            if db_sub.status != 'active':
                db_sub.status = 'active'
                db.commit()
                logger.info(f"Subscription {db_sub.id} reactivated after successful invoice payment.")
            
            customer = db.query(Customer).filter(Customer.id == db_sub.customer_id).first()
            
            logger.info(
                f"Invoice {invoice.id} paid for subscription {db_sub.id}. "
                f"Amount: {invoice.amount_paid/100} {invoice.currency.upper()}"
            )
            
            if customer:
                # TODO: Send payment receipt email
                logger.info(f"Payment receipt for {customer.email}: Invoice {invoice.id}")
        else:
            # Subscription not in database yet - this is OK for new subscriptions
            # The subscription will be created when customer.subscription.created fires
            logger.info(
                f"Subscription {subscription_id} not found in database for invoice {invoice.id}. "
                f"This is expected for new subscriptions. Amount: {invoice.amount_paid/100} {invoice.currency.upper()}"
            )
    except Exception as e:
        # Log error but don't raise - allow webhook to succeed
        logger.error(f"Error processing invoice.payment_succeeded for {invoice.id}: {str(e)}")
        # Don't re-raise - we want to return 200 OK to Stripe


def handle_invoice_payment_failed(db: Session, event: stripe.Event):
    """Handle failed invoice payment (for subscriptions)"""
    invoice = event.data.object
    subscription_id = _get_subscription_id_from_invoice(invoice)

    if not subscription_id:
        logger.info(f"Invoice {invoice.id} payment failed but not related to a subscription.")
        return
    
    try:
        db_sub = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()
        
        if db_sub:
            # Update subscription to past_due
            db_sub.status = 'past_due'
            db.commit()
            
            customer = db.query(Customer).filter(Customer.id == db_sub.customer_id).first()
            
            logger.warning(
                f"Invoice {invoice.id} FAILED for subscription {db_sub.id}. "
                f"Amount: {invoice.amount_due/100} {invoice.currency.upper()}, "
                f"Attempt: {invoice.attempt_count}"
            )
            
            if customer:
                # TODO: Send payment failure notification
                logger.warning(
                    f"Payment failure notification needed for {customer.email}. "
                    f"Subscription {db_sub.id} is now past_due."
                )
                
                # TODO: Integrate with email service
                # send_email(
                #     to=customer.email,
                #     subject="Payment Failed - Action Required",
                #     body=f"Your subscription payment failed. Please update your payment method."
                # )
        else:
            logger.warning(
                f"Subscription {subscription_id} not found for failed invoice {invoice.id}. "
                f"This may be a test invoice or subscription not yet in database."
            )
    except Exception as e:
        # Log error but don't raise - allow webhook to succeed
        logger.error(f"Error processing invoice.payment_failed for {invoice.id}: {str(e)}")
        # Don't re-raise - we want to return 200 OK to Stripe

# ============================================================================
# TRANSFER HANDLERS
# ============================================================================

def handle_transfer_created(db: Session, event: stripe.Event):
    """Stripe confirmed transfer creation — sync stripe_transfer_id and status."""
    from app.repositories.transfer_repository import transfer as transfer_repo
    from app.repositories.connected_account_repository import connected_account as ca_repo
    stripe_transfer = event.data.object

    # Try to find by stripe_transfer_id first
    db_transfer = transfer_repo.get_by_stripe_transfer_id(db, stripe_transfer.id)
    
    # If not found, try to find by local_transfer_id in metadata
    if not db_transfer and hasattr(stripe_transfer, 'metadata') and stripe_transfer.metadata:
        local_transfer_id = stripe_transfer.metadata.get('local_transfer_id')
        if local_transfer_id:
            db_transfer = transfer_repo.get(db, int(local_transfer_id))
    
    if db_transfer:
        # Update transfer with Stripe ID if not already set
        transfer_repo.update(db, db_obj=db_transfer, obj_in={
            "stripe_transfer_id": stripe_transfer.id,
            "status": "pending",
        })
        
        # Update connected account balance
        stripe_account_id = stripe_transfer.destination
        if stripe_account_id:
            db_account = ca_repo.get_by_stripe_account_id(db, stripe_account_id)
            if db_account:
                # Add transfer amount to connected account balance
                current_balance = getattr(db_account, 'balance_cents', 0) or 0
                new_balance = current_balance + stripe_transfer.amount
                ca_repo.update(db, db_obj=db_account, obj_in={
                    "balance_cents": new_balance
                })
                logger.info(
                    f"Updated ConnectedAccount {db_account.id} balance: "
                    f"${current_balance/100:.2f} → ${new_balance/100:.2f}"
                )
        
        logger.info(
            f"✅ Transfer {db_transfer.id} confirmed by Stripe — "
            f"ID: {stripe_transfer.id}, Amount: ${stripe_transfer.amount/100:.2f} {stripe_transfer.currency.upper()}"
        )
    else:
        logger.warning(f"⚠️  transfer.created webhook: no local record for Stripe transfer {stripe_transfer.id}")


def handle_transfer_updated(db: Session, event: stripe.Event):
    """Handle transfer status updates from Stripe."""
    from app.repositories.transfer_repository import transfer as transfer_repo
    stripe_transfer = event.data.object

    db_transfer = transfer_repo.get_by_stripe_transfer_id(db, stripe_transfer.id)
    if not db_transfer:
        logger.warning(f"transfer.updated webhook: no local record for Stripe transfer {stripe_transfer.id}")
        return

    # Derive status from Stripe transfer object
    # Stripe Transfer has no explicit 'status' field — infer from reversed flag
    new_status = "reversed" if stripe_transfer.reversed else "pending"
    transfer_repo.update(db, db_obj=db_transfer, obj_in={"status": new_status})
    logger.info(f"Transfer {db_transfer.id} updated — status={new_status}")


def handle_transfer_reversed(db: Session, event: stripe.Event):
    """Handle transfer reversal — funds returned from connected account to platform."""
    from app.repositories.transfer_repository import transfer as transfer_repo
    from app.repositories.connected_account_repository import connected_account as ca_repo
    from datetime import datetime, timezone
    stripe_transfer = event.data.object

    db_transfer = transfer_repo.get_by_stripe_transfer_id(db, stripe_transfer.id)
    if not db_transfer:
        logger.warning(f"transfer.reversed webhook: no local record for Stripe transfer {stripe_transfer.id}")
        return

    amount_reversed = stripe_transfer.amount_reversed
    is_full = (amount_reversed >= stripe_transfer.amount)

    transfer_repo.update(db, db_obj=db_transfer, obj_in={
        "status": "reversed" if is_full else "partially_reversed",
        "amount_reversed_cents": amount_reversed,
        "reversed_at": datetime.now(timezone.utc).isoformat(),
    })
    
    # Update connected account balance - subtract reversed amount
    stripe_account_id = stripe_transfer.destination
    if stripe_account_id:
        db_account = ca_repo.get_by_stripe_account_id(db, stripe_account_id)
        if db_account:
            current_balance = getattr(db_account, 'balance_cents', 0) or 0
            new_balance = current_balance - amount_reversed
            ca_repo.update(db, db_obj=db_account, obj_in={
                "balance_cents": new_balance
            })
            logger.info(
                f"Updated ConnectedAccount {db_account.id} balance after reversal: "
                f"${current_balance/100:.2f} → ${new_balance/100:.2f}"
            )
    
    logger.info(
        f"Transfer {db_transfer.id} reversed — "
        f"Amount reversed: ${amount_reversed/100:.2f} {stripe_transfer.currency.upper()}, "
        f"Full reversal: {is_full}"
    )


# ============================================================================
# PAYOUT HANDLERS
# ============================================================================

def handle_payout_created(db: Session, event: stripe.Event):
    """Handle payout.created webhook event."""
    from app.repositories.payout_repository import payout as payout_repo, PayoutCreate
    from app.repositories.connected_account_repository import connected_account as ca_repo
    from datetime import datetime, timezone

    stripe_payout = event.data.object
    payout_id = stripe_payout.id

    # Check if payout already exists
    existing_payout = payout_repo.get_by_stripe_payout_id(db, payout_id)
    if existing_payout:
        logger.info(f"Payout {payout_id} already exists. Skipping.")
        return

    # Get connected account
    stripe_account_id = event.account if hasattr(event, 'account') else None
    if not stripe_account_id:
        logger.warning(f"No connected account ID for payout {payout_id}")
        return

    db_account = ca_repo.get_by_stripe_account_id(db, stripe_account_id)
    if not db_account:
        logger.warning(f"Connected account {stripe_account_id} not found")
        return

    # Create payout record
    db_payout = payout_repo.create(db, obj_in=PayoutCreate(
        stripe_payout_id=payout_id,
        connected_account_id=db_account.id,
        amount_cents=stripe_payout.amount,
        currency=stripe_payout.currency,
        status=stripe_payout.status,
        arrival_date=datetime.fromtimestamp(stripe_payout.arrival_date, tz=timezone.utc) if stripe_payout.arrival_date else None,
        payout_type="standard",
        description=getattr(stripe_payout, 'description', None),
    ))

    # Update connected account balance - subtract payout amount
    current_balance = getattr(db_account, 'balance_cents', 0) or 0
    new_balance = current_balance - stripe_payout.amount
    ca_repo.update(db, db_obj=db_account, obj_in={
        "balance_cents": new_balance
    })

    logger.info(
        f"Payout {db_payout.id} created: ${db_payout.amount} {db_payout.currency.upper()}, "
        f"Account {db_account.id} balance: ${current_balance/100:.2f} → ${new_balance/100:.2f}"
    )


def handle_payout_paid(db: Session, event: stripe.Event):
    """Handle payout.paid webhook event."""
    from app.repositories.payout_repository import payout as payout_repo
    from datetime import datetime, timezone

    stripe_payout = event.data.object
    payout_id = stripe_payout.id

    db_payout = payout_repo.get_by_stripe_payout_id(db, payout_id)
    if not db_payout:
        logger.warning(f"Payout {payout_id} not found")
        return

    payout_repo.update(db, db_obj=db_payout, obj_in={
        "status": "paid",
        "arrival_date": datetime.fromtimestamp(stripe_payout.arrival_date, tz=timezone.utc) if stripe_payout.arrival_date else None,
    })

    logger.info(f"Payout {db_payout.id} PAID: ${db_payout.amount}")


def handle_payout_failed(db: Session, event: stripe.Event):
    """Handle payout.failed webhook event."""
    from app.repositories.payout_repository import payout as payout_repo

    stripe_payout = event.data.object
    payout_id = stripe_payout.id

    db_payout = payout_repo.get_by_stripe_payout_id(db, payout_id)
    if not db_payout:
        logger.warning(f"Payout {payout_id} not found")
        return

    failure_code = getattr(stripe_payout, 'failure_code', 'unknown')
    failure_message = getattr(stripe_payout, 'failure_message', 'No failure message')

    payout_repo.update(db, db_obj=db_payout, obj_in={
        "status": "failed",
        "failure_code": failure_code,
        "failure_message": failure_message,
    })

    logger.error(f"Payout {db_payout.id} FAILED: {failure_code} - {failure_message}")


# ============================================================================
# CONNECTED ACCOUNT HANDLERS
# ============================================================================

def handle_account_updated(db: Session, event: stripe.Event):
    """
    Sync connected account onboarding status when Stripe fires account.updated.
    This fires when the vendor completes the Express onboarding flow.
    """
    from app.repositories.connected_account_repository import connected_account as ca_repo
    stripe_account = event.data.object

    db_account = ca_repo.get_by_stripe_account_id(db, stripe_account.id)
    if not db_account:
        # Not a connected account we manage — safely ignore
        logger.debug(f"account.updated: {stripe_account.id} not in local DB, skipping")
        return

    charges_enabled = stripe_account.charges_enabled
    payouts_enabled = stripe_account.payouts_enabled
    details_submitted = stripe_account.details_submitted
    new_status = "active" if (charges_enabled and payouts_enabled) else "pending"

    ca_repo.update(db, db_obj=db_account, obj_in={
        "charges_enabled": charges_enabled,
        "payouts_enabled": payouts_enabled,
        "details_submitted": details_submitted,
        "status": new_status,
    })

    logger.info(
        f"ConnectedAccount {db_account.id} ({stripe_account.id}) updated — "
        f"status={new_status}, charges_enabled={charges_enabled}, payouts_enabled={payouts_enabled}"
    )


# ============================================================================
# EVENT DISPATCHER
# ============================================================================

def handle_payment_intent_created(db: Session, event: stripe.Event):
    """Handle newly created payment intent - informational only.

    A freshly created PaymentIntent is not yet captured or confirmed, so no
    DB write is needed here.  The authoritative state change happens when
    payment_intent.succeeded / payment_intent.payment_failed fires.
    """
    intent = event.data.object
    logger.info(
        f"PaymentIntent {intent.id} created. "
        f"Amount: {intent.amount / 100:.2f} {intent.currency.upper()}, "
        f"Status: {intent.status}"
    )


EVENT_HANDLERS = {
    # Checkout Session Events
    'checkout.session.completed': handle_checkout_session_completed,

    # Customer Events
    'customer.created': handle_customer_created,

    # Payment Intent Events
    'payment_intent.created': handle_payment_intent_created,
    'payment_intent.succeeded': handle_payment_intent_succeeded,
    'payment_intent.payment_failed': handle_payment_intent_failed,
    'payment_intent.canceled': handle_payment_intent_canceled,

    # Subscription Events
    'customer.subscription.created': handle_subscription_created,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'customer.subscription.trial_will_end': handle_subscription_trial_will_end,

    # Charge Events (Refunds & Disputes)
    'charge.refunded': handle_charge_refunded,
    'charge.dispute.created': handle_charge_dispute_created,

    # Invoice Events (Subscription Billing)
    'invoice.payment_succeeded': handle_invoice_payment_succeeded,
    'invoice.payment_failed': handle_invoice_payment_failed,

    # Transfer Events
    'transfer.created': handle_transfer_created,
    'transfer.updated': handle_transfer_updated,
    'transfer.reversed': handle_transfer_reversed,

    # Payout Events
    'payout.created': handle_payout_created,
    'payout.paid': handle_payout_paid,
    'payout.failed': handle_payout_failed,

    # Connected Account Events
    'account.updated': handle_account_updated,
}

def process_webhook_event(db: Session, event: stripe.Event):
    """
    Process webhook events with improved idempotency handling.
    
    Idempotency strategy:
    1. Check if event was already processed successfully
    2. If processing, check if it's stuck (timestamp-based retry)
    3. Mark as 'processing' before handling
    4. Mark as 'completed' after success or 'failed' on error
    """
    event_id = event.id
    
    # Check idempotency
    existing_key = db.query(IdempotencyKey).filter(IdempotencyKey.key == event_id).first()
    
    if existing_key:
        if existing_key.status == 'completed':
            logger.info(f"Event {event_id} already processed successfully. Skipping.")
            return
        
        elif existing_key.status == 'processing':
            # Check if stuck (processing for more than 5 minutes)
            from datetime import datetime, timezone, timedelta
            time_diff = datetime.now(timezone.utc) - existing_key.updated_at.replace(tzinfo=timezone.utc)
            
            if time_diff < timedelta(minutes=5):
                logger.warning(f"Event {event_id} is currently being processed. Skipping duplicate.")
                return
            else:
                logger.warning(f"Event {event_id} stuck in processing for {time_diff}. Retrying...")
                existing_key.attempts += 1
                existing_key.status = 'processing'
                db.commit()
        
        elif existing_key.status == 'failed':
            # Retry failed events
            logger.info(f"Retrying previously failed event {event_id} (attempt {existing_key.attempts + 1})")
            existing_key.attempts += 1
            existing_key.status = 'processing'
            existing_key.error_message = None
            db.commit()
    else:
        # Create new idempotency key in 'processing' state
        idempotency_key = IdempotencyKey(
            key=event_id,
            status='processing',
            attempts=1
        )
        db.add(idempotency_key)
        db.commit()
        existing_key = idempotency_key
    
    # Get the appropriate handler
    handler = EVENT_HANDLERS.get(event.type)
    
    if handler:
        logger.info(f"Dispatching event {event.type} (ID: {event_id})")
        try:
            # Execute the handler
            handler(db, event)
            
            # Mark as completed
            existing_key.status = 'completed'
            existing_key.error_message = None
            db.commit()
            
            logger.info(f"Successfully processed event {event_id}")
            
        except Exception as e:
            # Mark as failed
            existing_key.status = 'failed'
            existing_key.error_message = str(e)[:500]  # Truncate long errors
            db.commit()
            
            logger.error(f"Error processing event {event.type} (ID: {event_id}): {str(e)}", exc_info=True)
            raise  # Re-raise to return 500 to Stripe for retry
    else:
        # Unhandled event type - mark as completed to avoid reprocessing
        existing_key.status = 'completed'
        db.commit()
        logger.debug(f"Unhandled event type: {event.type} (ID: {event_id})")
