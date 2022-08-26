import time
import json
from pymongo import MongoClient
import requests
from fake_useragent import UserAgent
from decouple import config
import time
from tqdm import tqdm

cluster = MongoClient(
    f"mongodb://127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+1.5.4")
db = cluster["QuizDB"]

ANIME_API = 'https://api.jikan.moe/v3/anime/'  # Common API
TOP_API = 'https://api.jikan.moe/v3/top/anime/'  # TOP LIST API

user_agent = UserAgent()  # Getting user agent
headers = {'User-Agent': 'My User Agent 1.0'}  # Adding headers to request

db["Characters"].delete_many({})
for i in tqdm(range(1, 7)):
    json_text = requests.get(TOP_API + str(i) + "/bypopularity", headers)  # Send request and gets information about 'i' page of top
    characters_table = db["Characters"]  # Connect to Characters collection
    json_object = json.loads(json_text.text)
    top = json_object['top']  # Gets top anime list

    for anime in tqdm(top):
        time.sleep(1)  # Sleep between request because of limitation (3 per / sec)
        mal_id = anime['mal_id']  # Gets id of anime
        current_anime_json = requests.get(ANIME_API + str(mal_id) + '/characters_staff')  # Gets all characters of anime
        try:
            characters = json.loads(current_anime_json.text)['characters']  # Load all characters from json
        except KeyError:
            print("passed")
            pass
        except ConnectionRefusedError:
            print("passed")
            pass
        for character in characters:
            if character['role'] == 'Main':  # if it is main character
                if db["Characters"].count_documents({"id": character["mal_id"]}) == 0:  # And it not exist in DB
                    characters_table.insert_one({"id": character["mal_id"], "type": (i-1) // 2 + 1, "anime": anime["title"],
                                                 "img": character["image_url"], "name": character["name"],
                                                 "url": anime["url"]})  # Adding it

print("finished")
