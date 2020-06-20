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
from filter_news import filter_news, get_cities

# Init
newsapi = NewsApiClient(api_key="c89e608c4ae345e5a03cc1db04983b3a")
#newsapi = NewsApiClient(api_key='92f7976f22e94e109f47ef929d205515')

app = Flask(__name__)

app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

DATABASE_URL = os.environ['DATABASE_URL']

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/us")
def getUS():
	daysago = dt.datetime.now() - dt.timedelta(days=2)
	headlines = newsapi.get_everything(q="(coronavirus OR covid) AND (U.S. OR (united states) OR america OR american)", page_size=100, language='en',
                                       from_param=daysago.strftime("%Y-%m-%d"), sort_by="relevancy", 
                                       sources="New York Times, CNN, NBC News, The Washington Post, CNBC, Politico, Reuters")
	return get_cities(headlines)

@app.route("/trending/<state>")
def getTrending(state):
    print("STATE: " + state)
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

@app.route("/news/<state>/<county>")
def getNews(state, county = ''):
    print(f"state to query: {state}, county to query: {county}")  
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    query = f"SELECT * from news WHERE county = '{county}' AND state = '{state}';"
    cursor.execute(query)
    conn.commit()

    result = cursor.fetchall()
    # print(result)
    if (len(result) == 0 or len(result[0][3]['articles']) == 0):
        print("No entry found in database")
        if (state == 'Washington'):
            query_state = "Washington NOT DC NOT D.C."
        else:
            query_state = state
        weekago = dt.datetime.now() - dt.timedelta(days=7)
        headlines = newsapi.get_everything(q=query_state + ' AND \"' + county + '\" AND (coronavirus OR covid)', 
                                        page_size=100, language='en',
                                        from_param=weekago.strftime("%Y-%m-%d"), sort_by="relevancy")
        filtered_news = filter_news(headlines, state, county)

        # no record existed 
        if (len(result) == 0):
            query = """ INSERT INTO news (state, county, result, keywords) VALUES (%s,%s,%s,%s) """
            record = (state, county, json.dumps(headlines), filtered_news['keywords'])
            print("Row created")
        # record was empty
        else:
            query = """ UPDATE news SET result = %s, keywords = %s WHERE state = %s AND county = %s """
            record = (json.dumps(headlines), state, county, filtered_news['keywords'])
            print("Row updated")
        cursor.execute(query, record) 
        conn.commit()
    else:
        filtered_news = {'articles': result[0][3]['articles'], 'totalResults': result[0][3]['totalResults'], 'keywords': result[0][4]}
    
    cursor.close()
    conn.close()
    return filtered_news


if __name__ == "__main__":
    app.run(host='0.0.0.0',port=5000,debug=True)
