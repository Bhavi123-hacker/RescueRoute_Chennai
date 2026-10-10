"""Amazon Location Places search for Chennai pickup / hospital lookup."""
import os
import time

CITY_BIAS = {'Circle': {'Center': [80.2707, 13.0827], 'Radius': 35000}}

def search_places(query, max_results=8):
    if os.environ.get('ENABLE_LOCATION') != 'true':
        return 409, {'error': 'Place search requires AWS deployment with EnableLocation=true.'}
    text = (query or '').strip()
    if len(text) < 2:
        raise ValueError('Enter at least two characters to search places.')
    if len(text) > 120:
        raise ValueError('Place query is too long.')
    import boto3
    from botocore.config import Config
    client = boto3.client('geo-places', config=Config(connect_timeout=3, read_timeout=8, retries={'max_attempts': 1}))
    response = client.search_text(
        QueryText=text,
        MaxResults=min(max(1, int(max_results)), 10),
        BiasPosition=[80.2707, 13.0827],
        Filter={'BoundingBox': [80.05, 12.80, 80.35, 13.25]},
    )
    results = []
    for item in response.get('ResultItems', []):
        pos = item.get('Position') or []
        if len(pos) < 2:
            continue
        results.append({
            'place_id': item.get('PlaceId'),
            'label': item.get('Title') or item.get('Address', {}).get('Label', 'Place'),
            'address': item.get('Address', {}).get('Label', ''),
            'lon': pos[0],
            'lat': pos[1],
            'categories': [c.get('Name') for c in item.get('Categories', []) if c.get('Name')][:4],
        })
    return 200, {
        'source': 'AMAZON_LOCATION_PLACES',
        'query': text,
        'fetched_at': time.time(),
        'results': results,
        'notice': 'Place search is biased to the Chennai metro box. Confirm the pin before dispatch.',
    }
