# bot.py
import os
import discord
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
from asyncio import sleep
import requests

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
VERIFIED_ROLE_ID = int(os.getenv('VERIFIED_ROLE_ID'))
GUILD = None
VERIFIED_ROLE = None
ADMIN_ID = int(os.getenv('ADMIN_ID'))

client = discord.Client()

@client.event
async def on_ready():
    global GUILD
    for GUILD in client.guilds:
        if GUILD.id == GUILD_ID:
            break
    global VERIFIED_ROLE
    VERIFIED_ROLE = GUILD.get_role(VERIFIED_ROLE_ID)
    print('ready on server {}'.format(GUILD.name))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content == '-test':
        await test_function(message.author)
        return

    if message.content == '-authenticate':
        await cycle_authenticate(GUILD.get_member(message.author.id))
        return

    args = message.content.split()
    if args[0] == '-approve':
        if message.author.id != ADMIN_ID: return
        if len(args) not in {3,5}:
            await message.channel.send('Invalid command - expected 3 arguments, received {}'.format(len(args)))
        if args[1] == '-p':
            entity_type_id = 1
            entity_type_url = 'characters'
        elif args[1] == '-c':
            entity_type_id = 2
            entity_type_url = 'corporations'
        elif args[1] == '-a':
            entity_type_id = 3
            entity_type_url = 'alliances'
        else:
            await message.channel.send('Invalid command')
            return
        id = args[2]
        #  get pilot/corp/alliance information
        r = requests.get(url = 'https://esi.evetech.net/latest/{}/{}/?datasource=tranquility'.format(entity_type_url, id))
        data = r.json()
        if 'error' in data.keys():
            await message.channel.send(data['error'])
            return
        else:
            entity_name = data.get("name")
        if len(args) == 5 and args[3] == '-vouch': vouch = args[4]
        else: vouch = ''

        #  add new ally to DB
        try:
            connection = mysql.connector.connect(host='fspigel.mysql.pythonanywhere-services.com',
                                                 database='fspigel$default',
                                                 user='fspigel',
                                                 password='tuNRqcGcfx3UeaJ6B2TQ')
            if connection.is_connected():
                cursor = connection.cursor(prepared=True)
                statement = """INSERT INTO allies VALUES(%s, %s, %s, %s)"""
                payload = (id, entity_name, entity_type_id, vouch)
                cursor.execute(statement, payload)
                connection.commit()
        except Error as e:
            print("Error while connecting to MySQL", e)
            await message.channel.send("Error while connecting to MySQL: {}".format(e))
            return
        finally:
            if (connection.is_connected()):
                cursor.close()
                connection.close()
                print("MySQL connection is closed")

        await message.channel.send(f'{entity_name} has been successfully approved for this operation')
        return


@client.event
async def on_member_join(member):
    await cycle_authenticate(member)

async def test_function(member):
    return

async def authenticate(member):
    print(f'authentication attempt for {member.name}')
    response = check_membership(member.id)
    if response != False:
        full_data = get_full_data(response)
        ally_code = get_ally_code(full_data)
        print('ALLY CODE {}'.format(ally_code))
        if ally_code == 0:
            correct_nick = generate_discord_nick(response, ally_code)
            if member.nick != correct_nick: await member.edit(nick = correct_nick)
            await member.send(f"You have been authenticated as {correct_nick}, however your corp or alliance has not been approved for this operation. Please have your leadership contact someone from coordination.")
            return 1
        elif ally_code == 1:
            correct_nick = generate_discord_nick(response)
            if member.nick != correct_nick: await member.edit(nick = correct_nick)
            member_roles = [role.id for role in member.roles]
            if VERIFIED_ROLE_ID not in member_roles:
                await member.add_roles(VERIFIED_ROLE)
        elif ally_code == 2:
            correct_nick = generate_discord_nick(response, ally_code)
            if member.nick != correct_nick: await member.edit(nick = correct_nick)
            member_roles = [role.id for role in member.roles]
            if VERIFIED_ROLE_ID not in member_roles:
                await member.add_roles(VERIFIED_ROLE)
        elif ally_code == 3:
            correct_nick = generate_discord_nick(response, ally_code)
            if member.nick != correct_nick: await member.edit(nick = correct_nick)
            member_roles = [role.id for role in member.roles]
            if VERIFIED_ROLE_ID not in member_roles:
                await member.add_roles(VERIFIED_ROLE)
        await member.send("You have been authenticated and verified")
        return 1
    return 0

async def cycle_authenticate(member):
    response = await authenticate(member)
    if response == 0:
        await member.send('Please click on the following link and log in with your main character. Your request will time out in 60 seconds.\n{}'.format(generate_SSO_link(member.id)))
    for i in range(12):
        if response == 1: return
        print(f'attempt #{i+1}')
        response = await authenticate(member)
        await sleep(5)
    await member.send('Request to authenticate has timed out. Please try again later using `-authenticate`, or contact Tiger Venn Ronuken.')

def check_membership(discord_id):
    print('checking membership for {}'.format(discord_id))
    try:
        connection = mysql.connector.connect(host='fspigel.mysql.pythonanywhere-services.com',
                                             database='fspigel$default',
                                             user='fspigel',
                                             password='tuNRqcGcfx3UeaJ6B2TQ')
        if connection.is_connected():
            print('connected')
            cursor = connection.cursor()
            cursor.execute(f"SELECT * FROM users WHERE discord_id = {discord_id};")
            record = cursor.fetchall()
            if len(record) != 0: return record[0]
            else: return False
    except Error as e:
        print("Error while connecting to MySQL", e)
    finally:
        if (connection.is_connected()):
            cursor.close()
            connection.close()
            print("MySQL connection is closed")

def generate_discord_nick(row, ally_code=0):
    full_data = get_full_data(row)
    if ally_code in [0,1]:
        if full_data.get('alliance_id') != None:
            return f'''[{full_data.get('alliance_ticker')}] {full_data.get('character_name')}'''
        else:
            return f'''[{full_data.get('corporation_ticker')}] {full_data.get('character_name')}'''
    elif ally_code == 2:
        return f'''[{full_data.get('corporation_ticker')}] {full_data.get('character_name')}'''
    elif ally_code == 3:
        return f'''[{full_data.get('alliance_ticker')}] {full_data.get('character_name')}'''

def get_full_data(row):
    full_data = {
        'character_id' : row[1],
        'character_name' : row[2],
        'corporation_id' : row[3],
        'alliance_id' : row[4],
        'corporation_ticker' : row[5],
        'alliance_ticker' : row[6]
    }
    return full_data

def get_ally_code(full_data):
    try:
        connection = mysql.connector.connect(host='fspigel.mysql.pythonanywhere-services.com',
                                             database='fspigel$default',
                                             user='fspigel',
                                             password='tuNRqcGcfx3UeaJ6B2TQ')
        if connection.is_connected():
            print('connected')
            cursor = connection.cursor()

            # if player is in an alliance, check if alliance is whitelisted
            if full_data.get('alliance_id') != None:
                cursor.execute(f"SELECT COUNT(*) FROM allies WHERE entity_id = {full_data.get('alliance_id')};")
                result = cursor.fetchone()[0]
                print(result)
                if result != 0: return 3

            # check if corp is whitelisted
            cursor.execute(f"SELECT COUNT(*) FROM allies WHERE entity_id = {full_data.get('corporation_id')};")
            result = cursor.fetchone()[0]
            print(result)
            if result != 0: return 2

            # check if individual player is whitelisted
            cursor.execute(f"SELECT COUNT(*) FROM allies WHERE entity_id = {full_data.get('character_id')};")
            result = cursor.fetchone()[0]
            if result != 0: return 1

            # all whitelist checks have failed, player is not authorized
            return 0
    except Error as e:
        print("Error while connecting to MySQL", e)
    finally:
        if (connection.is_connected()):
            cursor.close()
            connection.close()

def generate_SSO_link(discord_id):
    redirect_string='https://login.eveonline.com/v2/oauth/authorize/?'\
                + 'response_type=code'\
                + '&redirect_uri=http%3A%2F%2Ffspigel.pythonanywhere.com%2Fcallback%2F'\
                + '&client_id=a495db7fd82f4caaaf0dc52968ae7595'\
                + '&state={}'.format(discord_id)
    return redirect_string

client.run(TOKEN)