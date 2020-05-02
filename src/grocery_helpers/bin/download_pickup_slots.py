import argparse
import logging
import os

from ..flyers import get_flyers


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()

    parser.add_argument('--postal_code',
                        default=os.environ.get('GH_POSTAL_CODE'),
                        help='postal code (default: '
                        '`GH_POSTAL_CODE` environment variable).')
    parser.add_argument('store', choices=('Real Canadian Superstore', 'Walmart'))
    parser.add_argument('location_name',
                        default=None,
                        help='Name of the store (default: '
                        'closest store).')
    parser.add_argument('--profile_dir',
                        default=os.environ.get('GH_PROFILE_DIR'),
                        help='Chrome user profile directory (default: '
                        '`GH_PROFILE_DIR` environment variable).')
    parser.add_argument('--output_data_dir',
                        default=os.environ.get('GH_OUTPUT_DATA_DIR'),
                        help='Output data directory (default: '
                        '`GH_OUTPUT_DATA_DIR` environment variable).')
    args = parser.parse_args()

    if args.output_data_dir == None:
        args.output_data_dir = '.'

    if args.store == 'Real Canadian Superstore':
        from .. import RealCanadianSuperstoreAPI
        api = RealCanadianSuperstoreAPI(data_directory=args.output_data_dir)
    elif args.store == 'Walmart':
        from .. import WalmartAPI
        api = WalmartAPI(data_directory=args.output_data_dir)
    
    df = api.get_pickup_slots(args.postal_code, args.location_name)
    print(df)
    