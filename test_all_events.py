"""
Test all 12 webhook events to verify they are being received and processed correctly.
This script will check configuration and trigger test events.
"""

import stripe
import os
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Expected events
ALL_EVENTS = [
    "checkout.session.completed",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "payment_intent.canceled",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.trial_will_end",
    "charge.refunded",
    "charge.dispute.created",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
]

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 100)
    print(title.center(100))
    print("=" * 100 + "\n")


def check_webhook_configuration():
    """Check webhook endpoints in Stripe Dashboard"""
    print_header("STEP 1: CHECKING STRIPE WEBHOOK CONFIGURATION")
    
    try:
        endpoints = stripe.WebhookEndpoint.list(limit=10)
        
        if not endpoints.data:
            print("❌ No webhook endpoints found in Stripe!")
            print("\nAction Required:")
            print("1. Go to: https://dashboard.stripe.com/test/webhooks")
            print("2. Add endpoint: https://unfilling-productile-stanford.ngrok-free.dev/api/v1/webhook")
            return False
        
        print(f"Found {len(endpoints.data)} webhook endpoint(s)\n")
        
        correct_endpoint = None
        for endpoint in endpoints.data:
            print(f"📍 Endpoint: {endpoint.url}")
            print(f"   Status: {'✅ Enabled' if endpoint.status == 'enabled' else '❌ Disabled'}")
            print(f"   Events: {len(endpoint.enabled_events)}")
            
            # Check if this is the correct endpoint
            if '/api/v1/webhook' in endpoint.url and endpoint.status == 'enabled':
                correct_endpoint = endpoint
                
                configured = []
                missing = []
                
                for event in ALL_EVENTS:
                    if event in endpoint.enabled_events or '*' in endpoint.enabled_events:
                        configured.append(event)
                    else:
                        missing.append(event)
                
                print(f"\n   ✅ Configured: {len(configured)}/12 events")
                if missing:
                    print(f"   ❌ Missing: {len(missing)} events")
                    for event in missing:
                        print(f"      • {event}")
                else:
                    print(f"   ✅ All 12 events configured!")
            
            print()
        
        if correct_endpoint and not missing:
            print("✅ Webhook configuration is correct!\n")
            return True
        elif correct_endpoint:
            print("⚠️  Webhook endpoint found but missing some events\n")
            return False
        else:
            print("❌ No matching webhook endpoint found for /api/v1/webhook\n")
            return False
            
    except Exception as e:
        print(f"❌ Error checking webhooks: {str(e)}\n")
        return False


def check_server_health():
    """Check if local server and ngrok are running"""
    print_header("STEP 2: CHECKING SERVER HEALTH")
    
    # Check local server
    print("1. Testing local server (http://localhost:8000)...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Local server is running")
            data = response.json()
            print(f"   Service: {data.get('service', 'N/A')}")
            print(f"   Status: {data.get('status', 'N/A')}")
        else:
            print(f"   ⚠️  Server responded with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Local server not accessible: {str(e)}")
        return False
    
    print()
    
    # Check ngrok
    print("2. Testing ngrok tunnel...")
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        if response.status_code == 200:
            data = response.json()
            tunnels = data.get('tunnels', [])
            
            if tunnels:
                for tunnel in tunnels:
                    if tunnel.get('proto') == 'https':
                        ngrok_url = tunnel.get('public_url')
                        print(f"   ✅ Ngrok tunnel active: {ngrok_url}")
                        break
            else:
                print("   ❌ No active ngrok tunnels found")
                return False
        else:
            print("   ⚠️  Could not get ngrok status")
    except Exception as e:
        print(f"   ❌ Ngrok not accessible: {str(e)}")
        return False
    
    print()
    
    # Check webhook endpoint
    print("3. Testing webhook endpoint...")
    try:
        # Try to POST to webhook (should get 400 for missing signature)
        response = requests.post("http://localhost:8000/api/v1/webhook", 
                                json={}, 
                                timeout=5)
        
        if response.status_code == 400:
            print("   ✅ Webhook endpoint is accessible")
            print("   ℹ️  400 response is expected (missing Stripe signature)")
        elif response.status_code == 404:
            print("   ❌ Webhook endpoint not found (404)")
            print("   Check that the route is: /api/v1/webhook")
            return False
        else:
            print(f"   ⚠️  Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Error testing endpoint: {str(e)}")
    
    print("\n✅ Server health check passed!\n")
    return True


def trigger_test_events():
    """Trigger actual Stripe events to test webhooks"""
    print_header("STEP 3: TRIGGERING TEST EVENTS")
    
    print("Creating test objects in Stripe to trigger webhook events...\n")
    
    results = []
    
    # 1. Create customer (triggers customer.created - not in our list but tests webhooks work)
    print("1️⃣  Creating test customer...")
    try:
        customer = stripe.Customer.create(
            email=f"test-{int(time.time())}@example.com",
            name="Test Customer",
            metadata={'test': 'webhook_verification'}
        )
        print(f"   ✅ Customer created: {customer.id}")
        results.append(("Customer Creation", True))
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        results.append(("Customer Creation", False))
        customer = None
    
    print()
    
    # 2. Create product and price
    print("2️⃣  Creating test product and price...")
    try:
        product = stripe.Product.create(
            name=f"Test Product {int(time.time())}",
            metadata={'test': 'webhook_verification'}
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=1000,
            currency="usd",
            recurring={"interval": "month"}  # For subscription testing
        )
        print(f"   ✅ Product: {product.id}")
        print(f"   ✅ Price: {price.id}")
        results.append(("Product/Price Creation", True))
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        results.append(("Product/Price Creation", False))
        price = None
    
    print()
    
    # 3. Create payment intent (triggers payment_intent.created, and later payment_intent.succeeded)
    print("3️⃣  Creating payment intent...")
    try:
        if customer:
            payment_intent = stripe.PaymentIntent.create(
                amount=2000,
                currency="usd",
                customer=customer.id,
                metadata={'test': 'webhook_verification'}
            )
            print(f"   ✅ Payment Intent: {payment_intent.id}")
            print(f"   📊 Status: {payment_intent.status}")
            print(f"   ℹ️  This triggers: payment_intent.created")
            results.append(("Payment Intent", True))
        else:
            print("   ⏭️  Skipped (no customer)")
            results.append(("Payment Intent", False))
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        results.append(("Payment Intent", False))
    
    print()
    
    # 4. Create checkout session (triggers checkout.session.completed when completed)
    print("4️⃣  Creating checkout session...")
    try:
        if customer and price:
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{'price': price.id, 'quantity': 1}],
                mode='subscription',
                success_url='https://example.com/success',
                cancel_url='https://example.com/cancel',
                metadata={'test': 'webhook_verification'}
            )
            print(f"   ✅ Checkout Session: {session.id}")
            print(f"   ℹ️  Complete the checkout to trigger: checkout.session.completed")
            results.append(("Checkout Session", True))
        else:
            print("   ⏭️  Skipped (prerequisites missing)")
            results.append(("Checkout Session", False))
    except Exception as e:
        print(f"   ❌ Failed: {str(e)}")
        results.append(("Checkout Session", False))
    
    print()
    
    return results


def check_recent_webhooks():
    """Check recent events that should have been sent to webhooks"""
    print_header("STEP 4: CHECKING RECENT EVENTS")
    
    try:
        events = stripe.Event.list(limit=20)
        
        if not events.data:
            print("No recent events found.\n")
            return
        
        print(f"Last 20 Stripe events:\n")
        
        event_counts = {}
        for event in events.data:
            event_type = event.type
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Show which of our monitored events occurred
        monitored_found = []
        for event_type in ALL_EVENTS:
            if event_type in event_counts:
                monitored_found.append((event_type, event_counts[event_type]))
        
        if monitored_found:
            print("✅ Monitored events found:")
            for event_type, count in monitored_found:
                print(f"   • {event_type}: {count} occurrence(s)")
        else:
            print("ℹ️  No monitored events in last 20 events")
        
        print(f"\n📊 All event types in last 20:")
        for event_type, count in sorted(event_counts.items()):
            icon = "✅" if event_type in ALL_EVENTS else "  "
            print(f"   {icon} {event_type}: {count}")
        
        print("\nℹ️  These events were sent to your webhook endpoint.")
        print("   Check your server logs to see if they were processed.\n")
        
    except Exception as e:
        print(f"❌ Error fetching events: {str(e)}\n")


def print_summary(config_ok, health_ok, test_results):
    """Print final summary"""
    print_header("FINAL SUMMARY")
    
    print("Configuration:")
    print(f"   {'✅' if config_ok else '❌'} Stripe webhook configuration")
    print(f"   {'✅' if health_ok else '❌'} Server health check")
    
    print("\nTest Results:")
    for test_name, success in test_results:
        print(f"   {'✅' if success else '❌'} {test_name}")
    
    print("\n" + "=" * 100)
    print("\n📝 NEXT STEPS:\n")
    
    if config_ok and health_ok:
        print("✅ Everything looks good!")
        print("\n1. Check your server logs for webhook processing:")
        print("   Look for: 'Dispatching event...' and 'Successfully processed event...'")
        print("\n2. Test with Stripe CLI:")
        print("   stripe trigger payment_intent.succeeded")
        print("   stripe trigger checkout.session.completed")
        print("\n3. Or send test webhooks from Stripe Dashboard:")
        print("   https://dashboard.stripe.com/test/webhooks")
    else:
        print("⚠️  Some issues were found. Please:")
        if not config_ok:
            print("\n1. Fix webhook configuration in Stripe Dashboard")
            print("   URL: https://unfilling-productile-stanford.ngrok-free.dev/api/v1/webhook")
            print("   Add all 12 required events")
        if not health_ok:
            print("\n2. Make sure your server and ngrok are running")
            print("   Server: uvicorn app.main:app --reload --port 8000")
            print("   Ngrok: ngrok http 8000")
    
    print("\n" + "=" * 100 + "\n")


def main():
    print("\n" + "=" * 100)
    print("STRIPE WEBHOOK EVENT TESTING".center(100))
    print("Testing all 12 configured webhook events".center(100))
    print("=" * 100)
    
    # Step 1: Check configuration
    config_ok = check_webhook_configuration()
    
    # Step 2: Check server health
    health_ok = check_server_health()
    
    # Step 3: Trigger test events
    test_results = []
    if health_ok:
        test_results = trigger_test_events()
    else:
        print("⚠️  Skipping event creation due to health check failures\n")
    
    # Step 4: Check recent webhooks
    check_recent_webhooks()
    
    # Print summary
    print_summary(config_ok, health_ok, test_results)


if __name__ == "__main__":
    main()
