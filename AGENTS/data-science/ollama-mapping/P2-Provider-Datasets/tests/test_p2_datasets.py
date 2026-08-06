import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {'digitalocean','lightsail','nocloudgpt'}
def load(p):
    with open(p, encoding='utf-8') as f: return json.load(f)
def json_files(): return sorted(ROOT.rglob('*.json'))
def test_all_json_parse():
    for p in json_files(): load(p)
def test_schema_files_exist():
    for name in ['provider-plans','deployment-templates','appliance-overhead','provider-indexes']:
        assert (ROOT/'schemas'/f'{name}.schema.json').exists()
def digitalocean_plans():
    out=[]
    for p in (ROOT/'providers/digitalocean').glob('*.json'): out.extend(load(p))
    return out
def lightsail_bundles(): return load(ROOT/'providers/lightsail/linux-unix-public-ipv4-bundles.json')
def test_unique_plan_identifiers():
    ids=[('digitalocean',p['plan_slug']) for p in digitalocean_plans()]+[('lightsail',b['bundle_id']) for b in lightsail_bundles()]
    assert len(ids)==len(set(ids))
def test_numeric_fields_are_valid():
    for p in digitalocean_plans():
        for k in ['vcpu','ram_gb','disk_gb','bandwidth_tb','monthly_price_usd','hourly_price_usd']:
            assert isinstance(p[k], (int,float)) and p[k] > 0
    for b in lightsail_bundles():
        for k in ['vcpu','ram_gb','disk_gb','transfer_tb','monthly_price_usd']:
            assert isinstance(b[k], (int,float)) and b[k] > 0
def test_valid_provider_identifiers():
    assert set(load(ROOT/'providers/common/metadata.json')['provider_identifiers']) == PROVIDERS
    assert {p['provider_id'] for p in load(ROOT/'indexes/providers.json')} == PROVIDERS
    assert {p['provider'] for p in digitalocean_plans()} == {'digitalocean'}
def test_required_metadata():
    for p in digitalocean_plans():
        for k in ['source_url','verified_at_utc','architecture','display_name','family']: assert k in p
    for b in lightsail_bundles():
        assert b['operating_system'] == 'Linux/Unix'
        assert 'Windows' not in b['display_name']
def test_index_consistency():
    summary=load(ROOT/'indexes/provider-summary.json')
    assert summary['digitalocean_plan_count'] == len(digitalocean_plans())
    assert summary['lightsail_bundle_count'] == len(lightsail_bundles())
    assert len(load(ROOT/'indexes/plans.json')) == len(digitalocean_plans()) + len(lightsail_bundles())
if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn(); print(f'PASS {name}')
