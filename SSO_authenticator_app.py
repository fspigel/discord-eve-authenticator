from flask import Flask, redirect, request
import requests
import base64
import json
from jose import jwt
from jose.exceptions import JWTClaimsError
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from os import getenv

app = Flask(__name__)

load_dotenv()
encryption_key = getenv('ENCRYPTION_KEY')

@app.route("/")
def hello():
    return ''


# @app.route("/authenticate/")
# def authenticate():
#     redirect_string='https://login.eveonline.com/v2/oauth/authorize/?'\
#                     + 'response_type=code'\
#                     + '&redirect_uri=http%3A%2F%2Ffspigel.pythonanywhere.com%2Fcallback%2F'\
#                     + '&client_id=a495db7fd82f4caaaf0dc52968ae7595'\
#                     + '&state={}'.format(request.args.get('discord_id'))
#     return redirect(redirect_string)


@app.route("/SSO/")  # https://docs.esi.evetech.net/docs/sso/web_based_sso_flow.html
def SSO_redirect():
    redirect_string='https://login.eveonline.com/v2/oauth/authorize/?'\
                    + 'response_type=code'\
                    + '&redirect_uri=http%3A%2F%2Ffspigel.pythonanywhere.com%2Fcallback%2F'\
                    + '&client_id=a495db7fd82f4caaaf0dc52968ae7595'\
                    + '&state=tempstring'
    return redirect(redirect_string)


@app.route("/callback/", methods=['GET'])
def callback():
    print('SSO conversation successful')
    code = request.args.get('code')
    state = request.args.get('state')
    decryptor = Fernet(encryption_key)
    try:
        discord_id = int(decryptor.decrypt(state.encode()))
    except Exception as e:
        print(f'An exception occured during handling of callback with state {state}:')
        print(e)
        return '<font face = "courier"><h1>Error</h1></font>'

    url = 'https://login.eveonline.com/v2/oauth/token'
    data = {
        'grant_type':'authorization_code',
        'code' : code
        }
    auth = base64.urlsafe_b64encode('a495db7fd82f4caaaf0dc52968ae7595:8557ZIdHYhXIrQ6uDhazARgSnlx7UlLdHn0AH0hN'.encode('utf-8')).decode()
    headers = {
        'Authorization' : 'Basic ' + auth,
        'Content-Type' : 'application/x-www-form-urlencoded',
        'Host' : 'login.eveonline.com'
    }

    print('generating POST request')
    print('url:')
    print(url)
    print('data:')
    print(data)
    print('headers:')
    print(headers)

    r = requests.post(url = url, data = data, headers = headers)
    print('POST request sent')
    print(type(r))
    print(r)
    print(r.text)
    json_obj = json.loads(r.text)
    print(json_obj['access_token'])
    print(json_obj.keys())
    jwt_token = json_obj['access_token']

    jwk_set_url = "https://login.eveonline.com/oauth/jwks"

    print('sending jwt GET request')
    res = requests.get(jwk_set_url)
    print('request sent successfully')
    res.raise_for_status()

    data = res.json()
    jwk_sets = data['keys']
    jwk_set = next((item for item in jwk_sets if item["alg"] == "RS256"))
    print('decoding...')

    try:
        data_decoded = jwt.decode(
            jwt_token,
            jwk_set,
            algorithms=jwk_set["alg"],
            issuer="login.eveonline.com"
        )
    except JWTClaimsError:
        try:
            data_decoded = jwt.decode(
                        jwt_token,
                        jwk_set,
                        algorithms=jwk_set["alg"],
                        issuer="https://login.eveonline.com"
                    )
        except:
            return '''<font face="courier"><h1>Failed</h1>
                      {}</font>'''.format(jwt_token)

    character_name = data_decoded['name']
    print('SSO authentication successful for {}'.format(character_name))
    print('retrieving character info')
    full_data = get_char_data(character_name)
    print(full_data)
    response = db_new_character_entry(full_data, discord_id)

    if response == 1:
        return '''<font face = "courier">
                    <h1>ERROR: The character {} has already been linked to a different
                    discord user.</h1>
                    If you weren't the one to authenticate using that character, your EVE account might be compromised.
                  </font>'''.format(full_data.get('character_name'))

    return f'''<font face = "courier">
            <h1>SSO Authentication successful!</h1>
            <h2>character: {full_data.get('character_name')}</h2>
            <h2>character_id: {full_data.get('character_id')}</h2>
            <h2>corporation: {full_data.get('corporation_ticker')}</h2>
            <h2>corporation_id: {full_data.get('corporation_id')}</h2>
            <h2>alliance: {full_data.get('alliance_ticker')}</h2>
            <h2>alliance_id: {full_data.get('alliance_id')}</h2>
            </br>
            </br>
            <h1>You may now close this tab.</h2>
          </font>'''


def get_char_data(character_name):
    print('retrieving character info for {}'.format(character_name))

    # get character_id
    request_char_id_url = 'https://esi.evetech.net/latest/universe/ids/?datasource=tranquility&language=en-us'
    request_char_id_data = '''[
                              "{}"
                             ]'''.format(character_name)
    r = requests.post(url = request_char_id_url, data = request_char_id_data)
    print(r)
    character_id = json.loads(r.text)['characters'][0]['id']

    # get alliance_id and corp_id
    request_corp_url = 'https://esi.evetech.net/latest/characters/{}/?datasource=tranquility'.format(character_id)
    print('request URL: {}'.format(request_corp_url))
    r = requests.get(url = request_corp_url)
    char_data = r.json()
    corporation_id = char_data.get('corporation_id')
    alliance_id = char_data.get('alliance_id')
    has_alliance = alliance_id != None

    # get alliance_tag and corp_tag
    print('requesting corp and alliance info')
    url='https://esi.evetech.net/latest/corporations/{}/?datasource=tranquility'.format(corporation_id)
    print('url: {}'.format(url))
    r = requests.get(url=url)
    corporation_ticker = r.json().get('ticker')
    if has_alliance:
        url='https://esi.evetech.net/latest/alliances/{}/?datasource=tranquility'.format(alliance_id)
        print('url: {}'.format(url))
        r = requests.get(url=url)
        alliance_ticker = r.json().get('ticker')
    else: alliance_ticker = ''

    full_data = {
        'character_id' : character_id,
        'character_name' : character_name,
        'corporation_id' : corporation_id,
        'corporation_ticker' : corporation_ticker,
        'has_alliance' : has_alliance,
        'alliance_id' : alliance_id,
        'alliance_ticker' : alliance_ticker
    }
    return full_data


def db_new_character_entry(full_character_data, discord_id):
    fd = full_character_data

    try:
        connection = mysql.connector.connect(host='fspigel.mysql.pythonanywhere-services.com',
                                             database='fspigel$default',
                                             user='fspigel',
                                             password='tuNRqcGcfx3UeaJ6B2TQ')
        if connection.is_connected():
            cursor = connection.cursor(prepared=True)

            # check if this character is already assigned to a user
            statement = """SELECT * FROM users WHERE character_id=%s"""
            payload = (fd.get('character_id'),)
            cursor.execute(statement, payload)
            record = cursor.fetchall()
            if len(record) != 0: return 1
            statement = """INSERT INTO users(discord_id, character_id, character_name, corporation_id, alliance_id, corporation_ticker, alliance_ticker)
                         VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            payload = (discord_id,
                fd.get('character_id'),
                fd.get('character_name'),
                fd.get('corporation_id'),
                fd.get('alliance_id'),
                fd.get('corporation_ticker'),
                fd.get('alliance_ticker')
                )
            cursor.execute(statement, payload)
            connection.commit()
            return 0
    except Error as e:
        print("Error while connecting to MySQL", e)
        return 2
    finally:
        if (connection.is_connected()):
            cursor.close()
            connection.close()
            print("MySQL connection is closed")


@app.route("/char_info_test/", methods=['POST', 'GET'])
def char_info_test():
    name = 'Tiger Venn Ronuken'
    print('retrieving character info')
    request_char_id_url = 'https://esi.evetech.net/latest/universe/ids/?datasource=tranquility&language=en-us'
    request_char_id_data = '''[
                              "{}"
                             ]'''.format(name)
    r = requests.post(url = request_char_id_url, data = request_char_id_data)
    print(type(r))
    print(r)
    print(r.text)
    char = json.loads(r.text)['characters'][0]

    request_corp_url = 'https://esi.evetech.net/latest/characters/{}/?datasource=tranquility'.format(char['id'])
    print('request URL: {}'.format(request_corp_url))
    r = requests.get(url = request_corp_url)
    char_data = r.json()

    return '''<font face = "courier">
                response: yes<br/>
                name: {}<br/>
                id: {}<br/>
                corp_id: {}<br/>
                alliance_id: {}
              </font>'''.format(char['name'], char['id'], char_data['corporation_id'], char_data['alliance_id'])


if __name__ == "__main__":
    app.run(debug=False)