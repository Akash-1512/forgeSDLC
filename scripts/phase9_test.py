import os

os.environ["SECRET_KEY"] = "validation-secret-key-32-chars-xx"

from subscription.tiers import ENTERPRISE, FREE, PRO, model_allowed_for_tier

print("Free models_allowed:", FREE.models_allowed)
assert model_allowed_for_tier("groq/llama-3.3-70b-versatile", FREE)
assert not model_allowed_for_tier("gpt-5.4", FREE)
assert model_allowed_for_tier("gpt-5.4-mini", PRO)
assert model_allowed_for_tier("gpt-5.4", ENTERPRISE)
print("Subscription tier gating: PASS")

from subscription.session_manager import create_session_token, verify_session_token

token = create_session_token("user-001", "pro")
print("Token (first 40):", token[:40], "...")
payload = verify_session_token(token)
print("Decoded payload:", payload)
assert payload["user_id"] == "user-001"
assert payload["tier"] == "pro"
print("JWT encode/decode: PASS")

