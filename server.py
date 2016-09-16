import sys
import requests, json
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)


@app.route('/')
def hello_world():
    return render_template("api.html")


@app.route('/hello')
def hello():
    return render_template('hello.html')


@app.route('/api/user')
def get_user():
    user = {
        'user_id': 'eugene',
        'name': 'Eugene'
    }
    return jsonify(user)


def get_menu_items_map(locu_id):
    res = requests.post(
        'https://api.locu.com/v2/venue/search',
        data=json.dumps({
            "api_key": "f165c0e560d0700288c2f70cf6b26e0c2de0348f",
            "fields": ["name", "menus"],
            "venue_queries": [
                {
                    "locu_id": locu_id,
                }
            ]
        })
    )
    venue = res.json().get('venues')[0]
    menu_items_map = {}
    for m in venue.get('menus'):
        menu_name = m.get('menu_item')
        for s in m.get('sections'):
            section_name = s.get('section_name').strip(u'\u200b').strip(u'\u200e')
            for sb in s.get('subsections'):
                for c in sb.get('contents'):
                    # if not menu_name:
                    #     print c.get('description')
                    if c.get('name'):
                        key = '%s - %s' % (section_name, c.get('name'))
                        menu_items_map.update({
                            key: {
                                'menu_name': menu_name,
                                'section_name': section_name,
                                'name': c.get('name'),
                                'ingredients': c.get('description')
                            }})
    return menu_items_map


def get_nutrient_data(usda_ndbno):
    res = requests.get(
        'http://api.nal.usda.gov/ndb/reports/?ndbno=%s&type=b&format=json&api_key=gkKkSgujfGRAVUtREOu7BTJkIKOk5K1as4wpm4Tn' % usda_ndbno
    )
    nutrients = res.json().get('report').get('food').get('nutrients')
    items = []
    for n in nutrients:
        if n.get('name') in ['Energy', 'Protein', 'Fiber, total dietary', 'Cholesterol', 'Vitamin C']:
            items.append({'name': n.get('name'),
                          'value': n.get('value')
                          })
    return items

def get_usda_data(ingredients):
    def get_usda_ndbno(food_item):
        res = requests.get(
            'http://api.nal.usda.gov/ndb/search/?format=json&q=%s&sort=r&ds=Standard Reference&max=5&offset=0&api_key=gkKkSgujfGRAVUtREOu7BTJkIKOk5K1as4wpm4Tn' % food_item
        )
        from pprint import pprint
        # pprint(res.json())
        try:
            res.json()
        except:
            return None
        if res.json().get('errors'):
            # print 'error'
            return None
        else:
            # usda_ndbno = res.json().get('list').get('item')[0].get('ndbno')
            # return {
            #     'name': food_item,
            #     'usda_name': res.json().get('list').get('item')[0].get('name'),
            #     'usda_no': usda_ndbno,
            #     'usda_link': 'https://ndb.nal.usda.gov/ndb/search/list?qlookup=%s' % usda_ndbno
            # }
            usda_ndbno = res.json().get('list').get('item')[0].get('ndbno')
            return get_nutrient_data(usda_ndbno)

    usda_data = {}
    for ingredient in ingredients:
        usda_data[ingredient] = get_usda_ndbno(ingredient)
    return usda_data
    # usda_datas = [get_usda_ndbno(f) for f in ingredients]
    # usda_datas = filter(lambda x: x, usda_datas)
    # return usda_datas


def parse_ingridents(val):
    ingredients = val.lower().split()
    ingredients = list(set(ingredients) - set(['with', 'and']))
    # ingredients = [v.strip(',') for v in ingredients]
    norm_ingridients = []
    for i in ingredients:
        i = i.strip(',').replace('croutons', 'crouton').replace('cheeses','cheese')
        norm_ingridients.append(i)
    return norm_ingridients


# populate the dict first

commodity_countries_stats_map = {}


def populate_countries_map():
    import csv
    with open('foodaidreport.csv') as file:
        reader = csv.reader(file)
        headers = reader.next()
        for row in reader:
            commodity = row[0].lower()
            countries_stats = []
            for h, v in zip(headers, row)[1:]:
                if float(v):
                    countries_stats.append({
                        "country": h,
                        "delivered-qty": float(v)
                    })
            commodity_countries_stats_map[commodity] = countries_stats
            # pprint(commodity_countries_stats_map)
            # commodity_countries_stats_map


populate_countries_map()


foodsupply_map = {}
def populate_foodsupply_map():
    import csv

    def get_num(float_str):
        try:
            return float(float_str)
        except:
            return 0

    with open('foodsupply.csv') as file:
        reader = csv.reader(file)
        headers = reader.next()
        for row in reader:
            # key = '%s-%s' % (row[0].lower(),row[1].lower())
            # foodsupply_map[key] = get_num(row[2])
            foodsupply_map.setdefault(row[0].lower(), {})[row[1].lower()] = get_num(row[2])
populate_foodsupply_map()


def get_foodaid_data(ingredients):
    foodaid_data = {}
    ingredient_to_foodaid_map = {
        'crouton': 'bread',
        'lettuce': 'fresh vegetables',
        'chicken': 'FRESH CHICKEN MEAT'.lower()
    }
    for ingredient in ingredients:
        foodaid_data[ingredient] = commodity_countries_stats_map.get(
            ingredient_to_foodaid_map.get(ingredient, ingredient))
    return foodaid_data


def get_foodsupply_data(ingredients):
    foodsupply_data = {}
    ingredient_to_foodsupply_map = {
        'crouton': 'wheat and products',
        'lettuce': 'vegetables',
        'chicken': 'Poultry Meat'.lower(),
        'cheese': 'Milk - Excluding Butter'.lower()
    }
    for ingredient in ingredients:
        s = foodsupply_map.get(
            ingredient_to_foodsupply_map.get(ingredient, ingredient))
        if s:
            foodsupply_data[ingredient] = {
                'food': s.get('food'),
                'processing': s.get('processing'),
                'production': s.get('production'),
                'waste': s.get('waste')
            }
        else:
            foodsupply_data[ingredient] = None
    return foodsupply_data


# @app.route('/api/details')
# def get_details():
#     locu_id = request.args.get('locu_id', '')
#     item_name = request.args.get('item_name', '')
#     print item_name
#
#     # menu_items = get_menu_items_map(locu_id)
#     # ingredients_str = menu_items.get(item_name).get('ingredients')
#     # ingredients = parse_ingridents(ingredients_str)
#     ingredients = ['cheese', 'crouton', 'pecorino', 'shaved', 'lettuce', 'homemade', 'romaine']
#
#     # usda_data = get_usda_data(ingredients)
#     usda_data = {}
#     foodsupply_data = get_foodsupply_data(ingredients)
#     foodaid_data = get_foodaid_data(ingredients)
#
#     datas = {
#         #        'item_info': menu_items.get(item_name),
#         'usda_data': usda_data,
#         'foodsupply_data': foodsupply_data,
#         'foodaid_data': foodaid_data,
#     }
#     return jsonify(datas)

@app.route('/api/details')
def get_details():
    locu_id = request.args.get('locu_id', '')
    item_name = request.args.get('item_name', '')
    print item_name

    menu_items = get_menu_items_map(locu_id)
    ingredients_str = menu_items.get(item_name).get('ingredients')
    if not ingredients_str:
        ingredients_str = menu_items.get(item_name).get('name')
    ingredients = parse_ingridents(ingredients_str)
    # ingredients = ['cheese', 'crouton', 'pecorino', 'shaved', 'lettuce', 'homemade', 'romaine']
    print ingredients

    # usda_data = {}
    usda_data = get_usda_data(ingredients)
    foodsupply_data = get_foodsupply_data(ingredients)
    foodaid_data = get_foodaid_data(ingredients)

    ingredients_map = {}
    for ingredient in ingredients:
        food_supply = foodsupply_data.get(ingredient)
        food_aid = foodaid_data.get(ingredient)
        usda = usda_data.get(ingredient)
        # if food_supply or food_aid or usda:
        if food_supply or food_aid:
            ingredient_data = {
                'food_supply': food_supply,
                'food_aid': food_aid,
                'usda': usda
            }
            ingredients_map[ingredient] = ingredient_data

    return jsonify(ingredients_map)


@app.route('/api/menus')
def get_menu_items():
    locu_id = request.args.get('locu_id', '')
    # menu_items = sorted(menu_items_map.keys())
    menu_items = get_menu_items_map(locu_id)
    # return jsonify(menu_items)
    return jsonify(sorted(menu_items.keys()))


@app.route('/api/restaurants')
def get_restaurants():
    query = request.args.get('query', '')
    print query

    data = {
        "api_key": "f165c0e560d0700288c2f70cf6b26e0c2de0348f",
        "fields": ["locu_id", "name", "location"],
        "venue_queries": [
            {
                "name": query,
                "menus": {"$present": True},
                "location": {
                    "geo": {
                        "$in_lat_lng_radius": [40.7610523, -73.9842797, 5000]
                    }
                }
            }
        ]
    }
    res = requests.post(
        'https://api.locu.com/v2/venue/search',
        data=json.dumps(data)
    )
    datas = [
        {
            'name': v.get('name'),
            'locu_id': v.get('locu_id'),
            'address': '%s, %s, %s' % (
                v.get('location').get('address1'), v.get('location').get('region'),
                v.get('location').get('postal_code')),
            'geo': v.get('location').get('geo').get('coordinates')
        } for v in res.json().get('venues')]
    return jsonify(datas)


@app.route('/api/items')
def get_menu_item():
    user = {
        'user_id': 'eugene',
        'name': 'Eugene'
    }
    return jsonify(user)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'dev':
        app.run(
            host="0.0.0.0",
            debug=True
        )
    else:
        app.run(
            host="0.0.0.0",
            threaded=True
        )
