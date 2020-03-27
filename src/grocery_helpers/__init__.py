import time
import tempfile
import json
import os
import urllib

import numpy as np
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException,
                                        ElementClickInterceptedException,
                                        StaleElementReferenceException)
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains


from ._version import get_versions
__version__ = get_versions()['version']
del get_versions


class Timeout(Exception):
    pass


class NoSearchResults(Exception):
    pass


def setup_and_teardown_driver(func):
        def wrapper(*args, **kwargs):
            self = args[0]
            if self._driver:
                close_driver = False
            else:
                self.init_driver()
                close_driver = True
            ret = func(*args, **kwargs)
            if close_driver:
                self.close_driver()
            return ret
        return wrapper

    
class GroceryHelpersAPI:

    def __init__(self, user=None, password=None, user_data_dir=None,
                 data_directory=os.path.join('.', 'data'),
                 base_url='https://www.realcanadiansuperstore.ca',
                 store_name='Real Canadian Superstore'):
        self._user = user
        self._password = password
        self._driver = None
        self._invoice_list = None
        self._temp_download_dir = tempfile.mkdtemp()
        self._user_data_dir = user_data_dir
        self._data_directory = os.path.join(data_directory,
                                            store_name)
        self._store_name = store_name
        self._base_url = base_url

    def __del__(self):
        self.close_driver()
        
    def init_driver(self, headless=False):
        options = webdriver.ChromeOptions()
        options.add_argument('window-size=1200x600')
        
        if self._user_data_dir:
            options.add_argument('user-data-dir=%s' % self._user_data_dir)

        if headless:
            options.add_argument('headless')

        self._driver = webdriver.Chrome(options=options)

    def close_driver(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    @setup_and_teardown_driver
    def search(self, term, timeout=10, follow_first_link=False):
        self._driver.get('%s/search?search-bar=%s' % (self._base_url, term))

        start_time = time.time()

        items = []
        while len(items) == 0 and time.time() - start_time < 10:
            items = self._driver.find_elements_by_class_name(
                'product-tile-group__item')
            product_data = [json.loads(item.find_element_by_class_name(
                'product-tracking').get_attribute('data-track-products-array'))
                            for item in items]
            links = self._driver.find_elements_by_class_name(
                'product-tile__details__info__name__link')
            
            if len(self._driver.find_elements_by_class_name(
                'search-no-results__section-title')):
                raise NoSearchResults
        
        df = pd.DataFrame()
        for field in ['productSKU', 'productName', 'productBrand',
                     'productCatalog', 'productVendor', 'productPrice',
                     'productQuantity', 'dealBadge', 'loyaltyBadge',
                     'textBadge', 'productPosition', 'productOrderId',
                     'productVariant']:
            df[field] = [data[0][field] for data in product_data]

        df['previouslyPurchased'] = ['Previously Purchased' in
                                     item.find_element_by_class_name(
                                         'product-tile__eyebrow'
                                     ).text for item in items]
        df['link'] = [link.get_attribute('href') for link in links]    
        df['categories'] = [urllib.request.unquote(link).replace('-', ' '). \
                            split('/')[4:-2] for link in df['link']]
        
        unit_price_list = []

        for item in items:
            unit_price = []
            for ul in item.find_elements_by_tag_name('ul'):
                for li in ul.find_elements_by_tag_name('li'):
                    data = [span.text for span in
                            li.find_elements_by_tag_name('span')]
                    if data[-1] == 'ea'  and len(data) == 5 and data[2] == '(est.)' and data[3] == '(est.)':
                        price = data[1]
                        quantity = data[4]
                    elif len(data) == 3:
                        price = data[1]
                        quantity = data[2]
                    else:
                        continue
                    unit_price.append((price, quantity))
            unit_price_list.append(unit_price)

        df['unitPrice'] = unit_price_list
        
        if follow_first_link and len(items):
            items[0].find_element_by_tag_name('a').click()
            
        return df

    @setup_and_teardown_driver
    def get_product_info(self, link=None, timeout=10):
        if link and self._driver.current_url != link:
            self._driver.get(link)
        elif link is None:
            link = self._driver.current_url
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                div = self._driver.find_element_by_class_name('product-tracking')
            except NoSuchElementException:
                pass
            
        product_data = json.loads(div.get_attribute('data-track-products-array'))[0]

        package_size = None
        try:
            package_size = div.find_element_by_class_name('product-name__item--package-size').text
        except:
            pass

        average_weight = None
        try:
            average_weight = div.find_element_by_class_name('product-avarage-weight--product-details-page').text
        except:
            pass

        items = div.find_elements_by_class_name('comparison-price-list__item')
        unit_price = [item.text for item in items]

        product_data['link'] = link
        product_data['categories'] = urllib.request.unquote(link).replace('-', ' ').split('/')[4:-2]
        product_data['packageSize'] = package_size
        product_data['averageWeight'] = average_weight
        product_data['unitPrice'] = unit_price

        return product_data

    @setup_and_teardown_driver
    def add_product_to_current_order(self, link, quantity=1, timeout=10):
        self._driver.get(link)
        self._driver.execute_script("window.scrollTo(0, 0);")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                product_details = self._driver.find_element_by_class_name('product-details-page-details')
            except NoSuchElementException:
                pass
        
        # If we've already added this item to the order, clear it
        try:
            input_box = self._driver.find_element_by_class_name('quantity-selector__quantity__input')
            input_box.click()
            ActionChains(self._driver).key_down(Keys.LEFT_CONTROL).send_keys('a').key_up(Keys.LEFT_CONTROL).perform()
            input_box.send_keys(0)
            input_box.send_keys(Keys.ENTER)
        except NoSuchElementException:
            pass        
        
        self._driver.find_element_by_css_selector(
            "button[data-track='productAddToCartButton']").click()
        time.sleep(1)

        input_box = self._driver.find_element_by_class_name('quantity-selector__quantity__input')
        input_box.click()
        ActionChains(self._driver).key_down(Keys.LEFT_CONTROL).send_keys('a').key_up(Keys.LEFT_CONTROL).perform()
        input_box.send_keys(quantity)
        input_box.send_keys(Keys.ENTER)
        
    @setup_and_teardown_driver
    def get_past_orders_list(self, timeout=10):
        self._driver.get(self._base_url + '/account/order-history')

        start_time = time.time()

        links = []
        while len(links) == 0 and time.time() - start_time < timeout:
            links = self._driver.find_elements_by_class_name('account-order-history-past-orders-delivery-list-item')
            dates = self._driver.find_elements_by_class_name('account-order-history-past-orders-delivery-list-item__details__date')
            prices = self._driver.find_elements_by_class_name('account-order-history-past-orders-delivery-list-item__price')

        dates = [date.text for date in dates]
        prices = [price.text for price in prices]
        links = [link.get_attribute('href') for link in links]
        order_numbers = [link.split('/')[-1] for link in links]
        
        df_orders = pd.DataFrame({'date': dates,
                                  'price': prices,
                                  'link': links,
                                  'orderNumber': order_numbers})
        return df_orders

    @setup_and_teardown_driver
    def get_itemized_order_history(self, timeout=10):
        df_orders = self.get_past_orders_list(timeout)
        
        orders_path = os.path.join(self._data_directory, 'orders.csv')

        if os.path.exists(orders_path):
            df = pd.read_csv(orders_path, index_col=0)
        else:
            df = pd.DataFrame()
        
        for i, link in enumerate(df_orders['link']):
            order_number = link.split('/')[-1]
            
            # skip if we've already downloaded this order
            if len(df) and int(order_number) in df['orderNumber'].values:
                continue
            
            self._driver.get(link)

            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    product_descriptions = self._driver. \
                        find_elements_by_class_name(
                        'order-history-details-products__product__info__name')
                except NoSuchElementException:
                    pass

            product_descriptions = [product_description.text for
                                    product_description in product_descriptions]

            product_skus = self._driver.find_elements_by_class_name(
                'order-history-details-products__product__info__code')
            product_skus = [product_sku.text for product_sku in product_skus]

            product_quantities = self._driver.find_elements_by_class_name(
                'order-history-details-products__product__quantity')
            product_quantities = [product_quantity.text for product_quantity
                                  in product_quantities]

            product_prices = self._driver.find_elements_by_class_name(
                'order-history-details-products__product__price')
            product_prices = [float(product_price.text[1:])
                              for product_price in product_prices]
            
            df_products = self.get_product_list()
            
            # add any new products to the products database
            for sku in product_skus:
                if len(df_products) == 0 or sku not in df_products.index:
                    try:
                        link = self.map_sku_to_link(sku)
                        self.add_product_to_database(link)
                    except NoSearchResults:
                        print("Couldn't find sku: %s" % sku)
            
            # Convert quantity field to units / kg
            units_list = []
            kg_list = []
            for j in range(len(product_quantities)):
                units = None
                kg = None
                try:
                    unit_price = product_quantities[j].split(' @ ')[1]
                    if unit_price.endswith(' ea'):
                        units =  product_prices[j] / float(unit_price[1:-3])
                        kg = units * df_products[product_skus[j] == df_products.index]['kg'].values[0]
                    elif unit_price.endswith(' /kg'):
                        kg = product_prices[j] / float(unit_price[1:-4])
                except IndexError:
                    pass
                units_list.append(units)
                kg_list.append(kg)

            df = df.append(pd.DataFrame({'description': product_descriptions,
                                         'productSKU': product_skus,
                                         'quantity': units_list,
                                         'kg': kg_list,
                                         'price': product_prices,
                                         'orderNumber': order_number,
                                         'date': df_orders['date'].values[i]}
            ), ignore_index=True)
            
            # update the orders database
            df.to_csv(orders_path)
            
        return df    

    @setup_and_teardown_driver
    def map_sku_to_link(self, sku, follow_link=True):
        # note errors with 100% maple syrup, 2% cottage cheese
        result = self.search(sku[:-3], follow_first_link=follow_link)
        if len(result) == 1:
            return result['link'].iloc[0]
        else:
            return None
    
    @setup_and_teardown_driver
    def add_product_to_database(self, link):
        products_path = os.path.join(self._data_directory, 'products', 'products.csv')

        if os.path.exists(products_path):
            df_products = pd.read_csv(products_path, index_col=0)
        else:
            df_products = pd.DataFrame()

        try:
            if np.isnan(link):
                link = None
        except TypeError:
            pass

        if len(df_products) and link in df_products['link'].values:
            return

        product_info = self.get_product_info(link)

        output_path = os.path.join(self._data_directory, product_info['productSKU'])

        if not os.path.exists(output_path):
            os.makedirs(output_path)

            with open(os.path.join(output_path, product_info['productName'] + '.html'), "wb") as f:
                f.write(self._driver.page_source.encode('utf-8'))

            src = self._driver.find_element_by_class_name('responsive-image--product-details-page').get_attribute('src')
            ext = os.path.splitext(src)[1]
            urllib.request.urlretrieve(src, os.path.join(output_path, product_info['productName'] + ext))

        data = {k: [v] for k, v in product_info.items()}
        
        def isnan(field):
            if field is None:
                return True
            try:
                return np.isnan(field)
            except TypeError:
                return False
        
        # Convert package size to weight (assume density of 1 kg/L for everything)
        x = data['packageSize'][0]
        kg = None
        if not isnan(data['averageWeight'][0]):
            kg = float(data['averageWeight'][0][18:-3])
        elif isnan(x):
            pass
        elif x.endswith(' mL'):
            kg = 1e-3 * float(x[:-3])
        elif x.endswith(' L'):
            kg = float(x[:-2])
        elif x.endswith(' kg'):
            kg = float(x[:-3])
        elif x.endswith(' lb'):
            kg = float(x[:-3]) / 2.2
        elif x.endswith(' lb bag'):
            kg = float(x[:-7]) / 2.2
        elif x.endswith(' g'):
            kg = 1e-3 * float(x[:-2])
        data['kg'] = [kg]
        
        sku = data.pop('productSKU')[0]
        df_products = df_products.append(pd.DataFrame(data, index=[sku]))
        df_products.to_csv(products_path)

    def get_product_list(self):
        products_path = os.path.join(self._data_directory, 'products', 'products.csv')
        if os.path.exists(products_path):
            return pd.read_csv(products_path, index_col=0)
        else:
            return pd.DataFrame()
    
    def _login(self):
        self._driver.get(self._base_url)
        self._driver.find_element_by_id("accessCode").send_keys(self._user)
        self._driver.find_element_by_id ("password").send_keys(self._password)
        self._driver.find_element_by_xpath('//*[@id="login-form"]/div[3]/button').click()


class RealCanadianSuperstoreAPI(GroceryHelpersAPI):
    def __init__(self, user=None, password=None, user_data_dir=None,
                 data_directory=os.path.join('.', 'data')):
        super().__init__(user=user, password=password, user_data_dir=user_data_dir,
                       data_directory=data_directory, 
                       base_url='https://www.realcanadiansuperstore.ca',
                       store_name='Real Canadian Superstore')


class LowblawsAPI(GroceryHelpersAPI):
    def __init__(self, user=None, password=None, user_data_dir=None,
                 data_directory=os.path.join('.', 'data')):
        super().__init__(user=user, password=password, user_data_dir=user_data_dir,
                       data_directory=data_directory, 
                       base_url='https://www.loblaws.ca',
                       store_name='Loblaws')

        
class ZehrsAPI(GroceryHelpersAPI):
    def __init__(self, user=None, password=None, user_data_dir=None,
                 data_directory=os.path.join('.', 'data')):
        super().__init__(user=user, password=password, user_data_dir=user_data_dir,
                       data_directory=data_directory, 
                       base_url='https://www.zehrs.ca',
                       store_name='Zehrs')

        
class ValumartAPI(GroceryHelpersAPI):
    def __init__(self, user=None, password=None, user_data_dir=None,
                 data_directory=os.path.join('.', 'data')):
        super().__init__(user=user, password=password, user_data_dir=user_data_dir,
                       data_directory=data_directory, 
                       base_url='https://www.valumart.ca',
                       store_name='Valu-mart')

        
class WalmartAPI(GroceryHelpersAPI):
    def __init__(self, user=None, password=None, user_data_dir=None,
                 data_directory=os.path.join('.', 'data')):
        super().__init__(user=user, password=password, user_data_dir=user_data_dir,
                       data_directory=data_directory, 
                       base_url='https://www.walmart.ca',
                       store_name='Walmart')

    @setup_and_teardown_driver
    def search(self, term, timeout=10, follow_first_link=False):
        self._driver.get('%s/search/%s' % (self._base_url, term))

        descriptions = self._driver.find_elements_by_class_name('description')
        descriptions = [description.text for description in descriptions]

        titles = self._driver.find_elements_by_class_name('title')
        titles = [title.text for title in titles][:len(descriptions)]
        
        price_units = self._driver.find_elements_by_class_name('price-unit')
        price_units = [price_unit.text for price_unit in price_units]

        prices = self._driver.find_elements_by_class_name('price-current')
        prices = [price.text.replace('\n', '') for price in prices]
        prices = [float(price[1:]) if price.find('¢') == -1 else float('0.%2d' % int(price[:-1])) for price in prices]

        skus = self._driver.find_elements_by_class_name('productSkus')
        data = [json.loads(sku.get_attribute('value')) for sku in skus]
        skus = [item['productid'] for item in data]

        links = self._driver.find_elements_by_class_name('product-link')
        links = [self._base_url + link.get_attribute('data-bind').split(',')[1][2:-3] for link in links]

        if follow_first_link and len(links):
            self._driver.get(links[0])
        
        df = pd.DataFrame({
         'sku': skus, 
         'title': titles,
         'description': descriptions,
         'unit_price': price_units,
         'price': prices,
         'link': links})

        return df
    
    
    @setup_and_teardown_driver
    def get_product_info(self, link=None, timeout=10):
        if link and self._driver.current_url != link:
            self._driver.get(link)
        elif link is None:
            link = self._driver.current_url

        json_data = [json.loads(script.get_attribute('innerHTML')) for script
                     in self._driver.find_elements_by_css_selector(
                         "script[type='application/ld+json']")]
        product = [x for x in json_data if x['@type'] == 'Product'][0]
        categories = [y['item']['name'] for y in
                      [x for x in json_data if x['@type'] == 'BreadcrumbList'
                      ][0]['itemListElement']][1:]
        ppu = self._driver.find_element_by_css_selector("span[data-automation='buybox-price-ppu']").text

        product_ids = {}
        div = self._driver.find_element_by_xpath("//*[contains(text(), 'Product Identifiers')]")
        for i in range(3):
            div = self._driver.execute_script("""
                return arguments[0].nextElementSibling
            """, div)
            field, value = div.text.split('\n')
            product_ids[field] = value

        product_info = {
            'name': product['name'],
            'description': product['description'],
            'brand': product['brand']['name'],
            'price': product['offers']['price'],
            'unit_price': ppu,
            'categories': categories
        }

        product_info.update(product_ids)
        
        return product_info
    
    @setup_and_teardown_driver
    def add_product_to_current_order(self, link, quantity=1, timeout=10):
        self._driver.get(link)

        input_box = self._driver.find_element_by_css_selector("span[data-automation='quantity']").find_element_by_tag_name('input')
        input_box.click()
        ActionChains(self._driver).key_down(Keys.LEFT_CONTROL).send_keys('a').key_up(Keys.LEFT_CONTROL).perform()
        input_box.send_keys(5)

        self._driver.find_element_by_xpath("//button[contains(text(), 'Add to cart')]").click()