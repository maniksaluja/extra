from pyrogram import Client

# Replace with your actual session string
session_string = "BQF0lboAcW3xr4pSLlwcg35NnGhsrXIFNoMVEyftP9M5m5mrN_WhmhhqVNWS2MiTBUsj34EykN_ENQ4Kgm8IuFVMRCae-6mlpM1m3zYLPd6Pn6gaet-aNgEtbedXrjOLRSMXCcwn6_ujVVIi2GBn9nQDNj_J6c527rvmIJ6LYra8MOoBk90T6E_me95ORsOfeyKaDyY_GMzK_Q7VRRv2IUwmH9HAm6SG4FBUerOpB5oVoVEqKXYAT8WbGZs3FsfP2Hr91mqQNs4tcv-6jfKPkuA9t4etrqC-Rqe6Awm5ezOPYIjy-r-CrkvpFTLRe_vsT2h12abCs826-bX3eV09hsI4UjNJjwAAAAF9OlgPAA"

# Replace with your actual API credentials
api_id = 24417722  # Replace with your API ID
api_hash = "68c75f726da6bd11acda8d7cd03e89f3"  # Replace with your API Hash

app = Client(session_string, api_id=api_id, api_hash=api_hash)

with app:
    me = app.get_me()
    print(f"User ID: {me.id}")
    print(f"Username: {me.username}")
    print(f"First Name: {me.first_name}")
    print(f"Phone Number: {me.phone_number}")
