import requests
import os
import glob

import pandas as pd
import arrow


BASE_URL = 'https://flipp.com'
BACKEND_URL = 'https://backflipp.wishabi.com/flipp'
SEARCH_URL = '%s/items/search' % BACKEND_URL
ITEM_URL = '%s/items/' % BACKEND_URL


def scrape_item(item_id):
    return requests.get(
        "%s/%s" % (ITEM_URL, item_id,)
    ).json()


def search(query, postal_code):
    return requests.get(
        SEARCH_URL,
        params = {
            'q': query,
            'postal_code': postal_code,
        }
    ).json()


def scrape_details(data, flyer_id=None):
    items = [
            scrape_item(x.get('flyer_item_id'))
            for x in data.get('items')
            if flyer_id is None or x.get('flyer_id') == flyer_id
    ]
    
    data = {}
    if len(items):
        # convert to pandas DataFrame
        for k in items[0]['item'].keys():
            data[k] = [item['item'][k] for item in items]
    return pd.DataFrame(data)


def get_flyers(merchant, postal_code, data_directory):
    data = search(merchant, postal_code)
    assert(merchant == data['merchants'][0]['name'])

    flyer_ids = [flyer['id'] for flyer in data['flyers']]

    flyers = []
    for flyer_id in flyer_ids:
        flyer_path = glob.glob(os.path.join(data_directory,
                                            merchant,
                                            'flyers',
                                            '*%s.csv' % flyer_id))
        if flyer_path:
            print('Already downloaded flyer %s for %s' % (flyer_id, merchant))
            flyers.append(pd.read_csv(flyer_path[0], index_col=0))
            continue

        print('Scrape flyer %s for %s' % (flyer_id, merchant))
        df = scrape_details(data, flyer_id)
        flyers.append(df)
        
        if len(df):
            dates = [arrow.get(date).date().isoformat() for date in
                     df.iloc[0][['flyer_valid_from', 'flyer_valid_to']].values.tolist()]
            merchant = df.iloc[0]['merchant']
            filepath = os.path.join(data_directory, merchant, 'flyers',
                                    '%s - %s flyer %s.csv' % (dates[1], merchant, flyer_id))

            if not os.path.exists(filepath):
                merchant_directory = os.path.join(data_directory, merchant, 'flyers')
                os.makedirs(merchant_directory, exist_ok=True)
                df.to_csv(filepath)
    return flyers