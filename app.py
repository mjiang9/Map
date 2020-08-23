from flask import Flask
from flask import render_template
from pymongo import MongoClient
import json
from bson import json_util
from bson.json_util import dumps
from newsapi import NewsApiClient
from flask_sqlalchemy import SQLAlchemy
import os
import psycopg2
import datetime as dt
from filter_news import filter_news, get_cities, countydict
import requests

# Init
newsapi = NewsApiClient(api_key="c89e608c4ae345e5a03cc1db04983b3a")
#newsapi = NewsApiClient(api_key='92f7976f22e94e109f47ef929d205515')

app = Flask(__name__)

app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

DATABASE_URL = os.environ['DATABASE_URL']

from_state = {'Alabama': 'al', 'Alaska': 'ak', 'American Samoa': 'as', 'Arizona': 'az', 'Arkansas': 'ar', 'California': 'ca', 'Colorado': 'co', 'Connecticut': 'ct', 'Delaware': 'de', 'District of Columbia': 'dc', 'Florida': 'fl', 'Georgia': 'ga', 'Guam': 'gu', 'Hawaii': 'hi', 'Idaho': 'id', 'Illinois': 'il', 'Indiana': 'in', 'Iowa': 'ia', 'Kansas': 'ks', 'Kentucky': 'ky', 'Louisiana': 'la', 'Maine': 'me', 'Maryland': 'md', 'Massachusetts': 'ma', 'Michigan': 'mi', 'Minnesota': 'mn', 'Mississippi': 'ms', 'Missouri': 'mo', 'Montana': 'mt', 'Nebraska': 'ne', 'Nevada': 'nv', 'New Hampshire': 'nh', 'New Jersey': 'nj', 'New Mexico': 'nm', 'New York': 'ny', 'North Carolina': 'nc', 'North Dakota': 'nd', 'Northern Mariana Islands': 'mp', 'Ohio': 'oh', 'Oklahoma': 'ok', 'Oregon': 'or', 'Pennsylvania': 'pa', 'Puerto Rico': 'pr', 'Rhode Island': 'ri', 'South Carolina': 'sc', 'South Dakota': 'sd', 'Tennessee': 'tn', 'Texas': 'tx', 'Utah': 'ut', 'Vermont': 'vt', 'Virgin Islands': 'vi', 'Virginia': 'va', 'Washington': 'wa', 'West Virginia': 'wv', 'Wisconsin': 'wi', 'Wyoming': 'wy'}

@app.route("/")
def index():
    return render_template("index.html")

def getlink(links):
    for l in links:
        if '.gov' in l:
            return l
    return links[0]

@app.route("/save/<input>")
def saveInput(input):
    print(input)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    query = f"INSERT INTO feedback (value) VALUES ('{input}');"
    cursor.execute(query)
    conn.commit()
    return ""

@app.route("/covidinfo")
def getCovidInfoAll():
    """unlimited requests I think"""
    to_state = {'AL': 'Alabama', 'AK': 'Alaska', 'AS': 'American Samoa', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'DC': 'District of Columbia', 'FL': 'Florida', 'GA': 'Georgia', 'GU': 'Guam', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'MP': 'Northern Mariana Islands', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'PR': 'Puerto Rico', 'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VI': 'Virgin Islands', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'}
    
    r = requests.get('https://covidtracking.com/api/states/info')
    info_json = r.json()
    info = {x['name']: getlink([x['covid19Site'], x['covid19SiteSecondary'], x['covid19SiteTertiary'], x['covid19SiteOld']]) for x in info_json}
    
    r = requests.get('https://covidtracking.com/api/states')
    counts_json = r.json()
    counts = {to_state[x['state']]: {'cases': x['positive'], 'deaths': x['death']} for x in counts_json}

    us = requests.get('https://covidtracking.com/api/v1/us/current.json').json()
    info['USA'] = 'https://www.coronavirus.gov/'
    counts['USA'] = {'cases': us[0]['positive'], 'deaths': us[0]['death']}

    return {'info': info, 'counts': counts}

@app.route("/covidinfo/<state>")
def getCovidInfo(state):
    info, counts = {}, {}
    us = requests.get('https://covidtracking.com/api/v1/us/current.json').json()
    info['USA'] = 'https://www.coronavirus.gov/'
    counts['USA'] = {'cases': us[0]['positive'], 'deaths': us[0]['death']}

    if state == 'United States':
        return {'info': info, 'counts': counts}

    r = requests.get(f'https://covidtracking.com/api/v1/states/{from_state[state]}/info.json')
    x = r.json()
    info[state] = getlink([x['covid19Site'], x['covid19SiteSecondary'], x['covid19SiteTertiary'], x['covid19SiteOld']])
    
    r = requests.get(f'https://covidtracking.com/api/v1/states/{from_state[state]}/current.json')
    x = r.json()
    counts[state] = {'cases': x['positive'], 'deaths': x['death']}

    return {'info': info, 'counts': counts}

@app.route("/covidhistory/<state>")
def getCovidHistory(state):
    if state == 'United States':
        r = requests.get('https://covidtracking.com/api/v1/us/daily.json')
    else:
        r = requests.get(f"https://covidtracking.com/api/v1/states/{from_state[state]}/daily.json")
    dates, cases, changes = [], [], []
    x = r.json()
    prev = 0
    for i in range(len(x)):
        date = x[len(x)-i-1] # it's given in reverse order, len(x)-i-1 is date of first case
        if not date['positive']:
            date['positive'] = prev
        dates.append(date['date']) # format: 20200621 means 2020 june 21
        cases.append(date['positive'])
        changes.append(date['positive'] - prev) # today - yesterday
        prev = date['positive']
    return {'dates': dates, 'cases': cases, 'changes': changes}

@app.route("/trending/<state>")
def getTrending(state):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    query = f"SELECT * from news WHERE county = '' AND state = '{state}';"
    cursor.execute(query)
    conn.commit()
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return {'keywords': result[0][4], 'articles': result[0][3]['articles']}

@app.route("/news/<state>")
def getStateNews(state):
    return getNews(state)

def getCountyQ(county, state):
    if (county, state) in countydict:
        ret = "(" + county
        for city in countydict[(county, state)]:
            ret += " OR " + city 
        return ret + ")" 
    return '\"' + county + '\"'

@app.route("/news/<state>/<county>")
def getNews(state, county = ''):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    query = f"SELECT * from news WHERE county = '{county}' AND state = '{state}';"
    cursor.execute(query)
    conn.commit()

    result = cursor.fetchall()
    if (len(result) == 0 or len(result[0][3]['articles']) == 0):
        print("No entry found in database")
        if (state == 'Washington'):
            query_state = '"Washington State" NOT DC NOT D.C.'
        else:
            query_state = state
        weekago = dt.datetime.now() - dt.timedelta(days=7)
        query_county = getCountyQ(county, state)
        print(query_county)
        headlines = newsapi.get_everything(q=query_state + ' AND ' + query_county + ' AND (coronavirus OR covid) NOT "reuters uk" NOT "reuters india" NOT "reuters canada"', 
                                        page_size=100, language='en',
                                        from_param=weekago.strftime("%Y-%m-%d"), sort_by="relevancy")
        filtered_news = filter_news(headlines, state, county)

        # no record existed 
        if (len(result) == 0):
            query = """ INSERT INTO news (state, county, result, keywords) VALUES (%s,%s,%s,%s) """
            record = (state, county, json.dumps({'totalResults': filtered_news['totalResults'], 'articles': filtered_news['articles']}), filtered_news['keywords'])
            print("Row created")
        # record was empty
        else:
            query = """ UPDATE news SET result = %s, keywords = %s WHERE state = %s AND county = %s """
            record = (json.dumps({'totalResults': filtered_news['totalResults'], 'articles': filtered_news['articles']}), filtered_news['keywords'], state, county)
            print("Row updated")
        cursor.execute(query, record) 
        conn.commit()
    else:
        filtered_news = {'articles': result[0][3]['articles'], 'totalResults': result[0][3]['totalResults'], 'keywords': result[0][4]}
    filtered_news['covinfo'] = getCovidInfo(state)
    cursor.close()
    conn.close()
    return filtered_news


if __name__ == "__main__":
    app.run(host='0.0.0.0',port=5000,debug=True)
