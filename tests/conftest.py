"""Global pytest configuration and test environment defaults for Keystone."""

import os

# Ensure required secrets are populated in test environments without relying on
# deleted hardcoded production fallbacks.
os.environ.setdefault("KEYSTONE_ENVELOPE_SECRET", "test-envelope-secret-for-pytest-only")
os.environ.setdefault("KEYSTONE_INTERNAL_SERVICE_TOKEN", "test-internal-service-token")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_stripe_webhook_secret")
os.environ.setdefault("KEYSTONE_C2PA_SIGNING_KEY", "test-c2pa-signing-key-for-pytest-only")
os.environ.setdefault("ADULT_PROCESSOR_WEBHOOK_SECRET", "whsec_test_adult_processor_secret")
