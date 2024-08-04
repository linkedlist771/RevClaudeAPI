
from rev_claude.configs import ROOT
import json 


key_configs_path = ROOT / "key_configs.json"

def load_key_configs():
    with open(key_configs_path, "r") as f:
        return json.load(f)




def get_poe_bot_api_key():
    return load_key_configs()["poe_bot_apikey"]