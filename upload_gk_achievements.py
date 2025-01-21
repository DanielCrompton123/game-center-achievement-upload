
# Python script to Upload achievements in an achievements.csv file to Game Center
# It ALSO automates translating the localizations for you too!
# NOTE: Usage and documentation links are for individual keys only

# VIDEO guide: https://developer.apple.com/videos/play/tech-talks/111377

import time
import jwt
import csv
import requests
import os
import re
import math
import translate



### /// CONSTANTS \\\ ###
# Edit these to meet your app

# Path to the Achievements CSV file
ACHIEVEMENTS_CSV_PATH = "/Users/daniel/Downloads/Achievements.csv"

# Wether the last record in the CSV file is a footer (whioch should not be converted into an Achievement)
ACHIEVEMENTS_CSV_LAST_ROW_IS_FOOTER = True

# Path to the .p8 APple API key
P8_APPLE_API_KEY_PATH = "/Users/daniel/Downloads/ApiKey_CPSN8ZSGUAVX.p8"

# Path to the root folder for the achievement images
ACHIEVEMENT_IMAGE_ROOT_PATH = "/Users/daniel/Downloads/Game kit icons"


# JWT lifespan (secs). You shouldn't need to edit this
JWT_LIFESPAN_SECS = 600 #(10m minutes)

# This is the Apple ID of your app. you can find it in your app in App Store connect > Sidebar > App Information > Apple ID
APP_ID = "6739331151"

# This is the Apple API key ID found in App store connect > Your profile > API keys > Key ID.
KEY_ID = "CPSN8ZSGUAVX"

# This is an array of all the language codes to translate to (descriptions and title will be translated).
# (1) = Language code (for translator module), (2) = Locale
# Use this: https://help.sap.com/docs/SAP_BUSINESSOBJECTS_BUSINESS_INTELLIGENCE_PLATFORM/09382741061c40a989fae01e61d54202/46758c5e6e041014910aba7db0e91070.html
DESTINATION_LANGUAGES = [("en", "en-GB"), ("es", "es-ES"), ("fr", "fr-FR"), ("de", "de-DE")]
# Spanish, Simplified Chinese, French/Canadian French, Germam, Japanese

# ERROR HERE: chinese, and japanese

# These are the CSV headers to get the relevant data from
CSV_ID_KEY = "ID"
CSV_TITLE_KEY = "Title"
CSV_POINTS_KEY = "Points"
CSV_DESCRIPTION_KEY = "Description"
CSV_EARNED_DESCRIPTION_KEY = "Earned description"
CSV_IMAGE_NAME_KEY = "Image name (.png)"
CSV_REPEATABLE_KEY = "Achievable multiple times"
CSV_HIDDEN_KEY = "Hidden"

# These are the values for TRUE for the repeatable and hidden
CSV_BOOL_TRUE_VALUE = "TRUE"



# Class declaration for the achievement
class Achievement:
	def __init__(self, id:str, title:str, points:int, description:str, earned_description:str, image_name:str, achievable_multiple_times:bool=False, hidden:bool=False):
		self.id = id
		self.title = title
		self.points = points
		self.description = description
		self.earned_description = earned_description
		self.image_name = image_name
		self.achievable_multiple_times = achievable_multiple_times
		self.hidden = hidden

	def full_path(self, image_relative_dir: str, extension:str="") -> str:
		return os.path.join(image_relative_dir, self.image_name + extension)

	def translated(self, dest_code) -> 'Achievement':

		# Use the translator module, first create a translator
		translator = translate.Translator(from_lang="en", to_lang=dest_code)

		# Now copy the achievement
		new_achievement = Achievement(
			id=self.id,
			title=translator.translate(self.title),
			points=self.points,
			description=translator.translate(self.description),
			earned_description=translator.translate(self.earned_description),
			image_name=self.image_name,
			achievable_multiple_times=self.achievable_multiple_times,
			hidden=self.hidden
		)

		return new_achievement



# List to accumulate errors. It will be saved later on
errors = []



def create_signed_jwt(p8_file_path: str) -> str:

	# 1. Download .p8 file from App store connect
	# 2. Create JWT:
		# 2.a. Create the header (https://developer.apple.com/documentation/appstoreconnectapi/generating-tokens-for-api-requests#Create-the-JWT-Header)
		# 2.b. Create the payload (https://developer.apple.com/documentation/appstoreconnectapi/generating-tokens-for-api-requests#Create-the-JWT-Payload-for-Individual-Keys)
		# 2.c. Sign the JWT with JWT module

	# Create the header
	jwt_header = {
		"alg": "ES256",
		"kid": KEY_ID,
		"typ": "JWT"
	}

	# Create the payload
	now = int(time.time())
	exp = now + JWT_LIFESPAN_SECS #The expiration time. The JWT shouldn't last longer than this.

	jwt_payload = {
		"sub": "user",
		"iat": now,
		"exp": exp,
		"aud": "appstoreconnect-v1"
	}

	# Now sign the JWT
	with open(p8_file_path, "r") as key_file:
		private_key = key_file.read()

	# Sign the JWT
	token = jwt.encode(
	    payload=jwt_payload,
	    key=private_key,
	    algorithm="ES256",
	    headers=jwt_header
	)

	print("Created signed JWT key")

	return token



def get_achievements(achievements_csv_path: str) -> list[Achievement]:

	# 1. Open the CSV file linked by the user
	# 2. Get the 2D array and put into objects
	# 3. Format the file name properly (using the .<ext> at the end of the CSV_IMAGE_NAME_KEY, putting that at the end of each image name in the cells)

	with open(achievements_csv_path) as data_file:
		print("Reading achievements from CSV...")
		reader = csv.DictReader(data_file)

		achievements = []

		reader_list =  list(reader)
		for (index, row) in enumerate(reader_list):

			if index == (len(reader_list) - 1) and ACHIEVEMENTS_CSV_LAST_ROW_IS_FOOTER:
				# This is the last element
				# Skip
				continue
			
			image_name = row.get(CSV_IMAGE_NAME_KEY)

			if match := re.search(r"\(([^)]+)\)$", CSV_IMAGE_NAME_KEY):

				# If the image name key from the CSV ends with brackets, we expect the image type can be found here. So let's append this onto the image name
				# But only append it if it's not already on the end of the image name
				content = match.group(1)

				if not image_name.endswith(content):
					image_name += content

			achievements.append(Achievement(
				id=row.get(CSV_ID_KEY),
				title=row.get(CSV_TITLE_KEY),
				points=int(row.get(CSV_POINTS_KEY)),
				description=row.get(CSV_DESCRIPTION_KEY),
				earned_description=row.get(CSV_EARNED_DESCRIPTION_KEY),
				image_name=image_name,
				achievable_multiple_times=row.get(CSV_REPEATABLE_KEY) == CSV_BOOL_TRUE_VALUE,
				hidden=row.get(CSV_HIDDEN_KEY) == CSV_BOOL_TRUE_VALUE
			))

		print(f"Retrieved {len(achievements)} from CSV file.\n")

		return achievements



def get_gc_detail_id(headers: dict) -> str:

	# A Game Center Detail id is needed to interface between the App and the Achievements
	# We would create one if game center was not already added. If game center IS added, we should instead get the detail ID

	# Get the GameCenter state
	# GET https://api.appstoreconnect.apple.com/v1/apps/{APP ID}/gameCenterDetail
	# https://developer.apple.com/documentation/appstoreconnectapi/get-v1-apps-_id_-gamecenterdetail

	gc_detail_state = f"https://api.appstoreconnect.apple.com/v1/apps/{APP_ID}/gameCenterDetail"

	response = requests.get(gc_detail_state, headers=headers)

	# print(f"Get GC detail: {response.status_code}\n{response.text}\n")
	print(f"Get GC detail: {response.status_code}. GC ID = {response.json().get('data').get('id')}")

	# Now if there was an error and the status code is no1 between 2-300, report it
	global errors
	if response.status_code < 200 or response.status_code > 300:
		errors.append(f"""
ERROR getting GameCenter details for an app:

{response.text}

- Make sure you enabled game center for this app
		""")

		return None

	return response.json().get("data").get("id") # This is the JSON path to the UUID



def create_achievement(achievement: Achievement, game_center_detail_id: str, headers:dict) -> str:
	global errors

	# POST https://api.appstoreconnect.apple.com/v1/gameCenterAchievements
	# Body = GameCenterAchievementCreateRequest

	gc_achievements_url = "https://api.appstoreconnect.apple.com/v1/gameCenterAchievements"

	achievement_create_request = {
		"data": {
			"attributes": {

				"points": achievement.points,
				"referenceName": achievement.title,
				"repeatable": achievement.achievable_multiple_times,
				"showBeforeEarned": not achievement.hidden,
				"vendorIdentifier": achievement.id

			},
			"relationships": {
				"gameCenterDetail": {
					"data": {
						"id": game_center_detail_id,
						"type": "gameCenterDetails"
					}
				}
			},
			"type": "gameCenterAchievements"
		}
	}

	# Now use requests to post the request and retrieve the response
	response = requests.post(gc_achievements_url, json=achievement_create_request, headers=headers)

	# print(f"Create GC achievements: {response.status_code}\n{response.text}\n")
	print(f"Create GC achievement {achievement.id}: {response.status_code}")

	# Now if there was an error and the status code is no1 between 2-300, report it
	global errors
	if response.status_code < 200 or response.status_code > 300:
		errors.append(f"""
ERROR creating achievement with ID {achievement.id}:

{response.text}
		""")

		return None

	# Now return the achievement ID
	return response.json().get("data").get("id")



def create_localization(locale: str, achievement: Achievement, achievement_id: str, headers: dict) -> str:

	# POST https://api.appstoreconnect.apple.com/v1/gameCenterAchievementLocalizations
	# https://developer.apple.com/documentation/appstoreconnectapi/post-v1-gamecenterachievementlocalizations

	localization_create = "https://api.appstoreconnect.apple.com/v1/gameCenterAchievementLocalizations"

	localization_create_request = {
		"data": {
			"type": "gameCenterAchievementLocalizations",
			"attributes": {

				"afterEarnedDescription": achievement.earned_description,
				"beforeEarnedDescription": achievement.description,
				"locale": locale,
				"name": achievement.title

			},
			"relationships": {
				"gameCenterAchievement": {
					"data": {
						"id": achievement_id,
						"type": "gameCenterAchievements"
					}
				}
			}
		}
	}

	# Now post the request
	response = requests.post(localization_create, json=localization_create_request, headers=headers)

	# print(f"Create localization: {response.status_code}\n{response.text}\n")
	print(f"Create localization {locale}: {response.status_code}")

	# Now if there was an error and the status code is no1 between 2-300, report it
	global errors
	if response.status_code < 200 or response.status_code > 300:
		errors.append(f"""
ERROR creating the localization {locale} for {achievement.id}:

{response.text}
		""")

		return None

	# Now return the ID for the localization
	return response.json().get("data").get("id")



def reserve_image_storage(file_path: str, localization_id: str, headers: dict) -> dict:

	# POST https://api.appstoreconnect.apple.com/v1/gameCenterAchievementImages
	# https://developer.apple.com/documentation/appstoreconnectapi/post-v1-gamecenterachievementimages

	# Firstly, get the full image path.
	# The achievement image name only contains the file name (with extension) not the path. so we should join it with the base to get the full path for App Store connect
	# We should also get the file size for the image in kilobytes, formatted properly

	image_create_url = "https://api.appstoreconnect.apple.com/v1/gameCenterAchievementImages"

	file_size = os.path.getsize(file_path)

	achievement_image_create_request = {
		"data": {
			"attributes": {
				"fileName": file_path,
				"fileSize": file_size
			},
			"relationships": {
				"gameCenterAchievementLocalization": {
					"data": {
						"id": localization_id,
						"type": "gameCenterAchievementLocalizations"
					}
				}
			},
			"type": "gameCenterAchievementImages"
		}
	}

	# Post the request
	response = requests.post(image_create_url, json=achievement_image_create_request, headers=headers)

	# print(f"Image reservation: {response.status_code}\n{response.text}\n")
	print(f"Image reservation: {response.status_code}")

	# Now if there was an error and the status code is no1 between 2-300, report it
	global errors
	if response.status_code < 200 or response.status_code > 300:
		errors.append(f"""
ERROR reserving image storage for image at {file_path}:

{response.text}
		""")

		return None

	return response.json()



def upload_image(upload_operation: dict, file_path: str):

	# The upload operations object in the image create response contains a URL to send a PUT request to that uploads the image.

	upload_url = upload_operation.get("url")
	upload_headers = upload_operation.get("requestHeaders")[0]

	# Now get the raw data for the image (to send)
	with open(file_path, "rb") as image_file:
		# Send PUT request
		response = requests.put(upload_url, data=image_file, headers=upload_headers)

		# print(f"Upload image: {response.status_code}\n{response.text}\n")
		print(f"Upload image: {response.status_code}")

		# No need to return an identifier as PUT does not give a JSON response

		# Now if there was an error and the status code is no1 between 2-300, report it
		global errors
		if response.status_code < 200 or response.status_code > 300:
			errors.append(f"""
ERROR uploading image data for achievement {achievement.id}:

{response.text}
			""")



def commit_image_addition(achievement_image_id: str, headers: dict):

	# PATCH https://api.appstoreconnect.apple.com/v1/gameCenterAchievementImages/{id}

	achievement_image_update_url = f"https://api.appstoreconnect.apple.com/v1/gameCenterAchievementImages/{achievement_image_id}"

	achievement_image_update_request = {
		"data": {
			"id": achievement_image_id,
			"type": "gameCenterAchievementImages",
			"attributes": {
				"uploaded": True
			}
		}
	}

	response = requests.patch(achievement_image_update_url, json=achievement_image_update_request, headers=headers)

	# print(f"Commit image addition {response.status_code}:\n{response.text}\n")
	print(f"Commit image addition {response.status_code}")

	# Now if there was an error and the status code is no1 between 2-300, report it
	global errors
	if response.status_code < 200 or response.status_code > 300:
		errors.append(f"""
ERROR committing image addition for achievement {achievement.id}:

{response.text}
		""")



def add_image(achievement: Achievement, image_relative_dir: str, localization_id: str, headers: dict):

	# Firstly, we create a reservation request to ask to save data on Apple
	# Then in the response we get a URL to do HTTP PIUT request to to upload data
	# Lasty, we can commit the imahge upload woth a PATCH request

	full_path = achievement.full_path(image_relative_dir)
	# print(f"Adding image from {full_path}\n")

	reserve_response_json = reserve_image_storage(full_path, localization_id, headers)

	upload_operations = reserve_response_json.get("data").get("attributes").get("uploadOperations")
	# print(f"upload_operations = {upload_operations}\n")

	upload_image(upload_operations[0], full_path)

	# Now commit the image addition by updating (patching) the Achievement image resource 'uploaded' property to true
	reserve_image_id = reserve_response_json.get("data").get("id")
	commit_image_addition(reserve_image_id, headers)



def test():

	ach = get_achievements(ACHIEVEMENTS_CSV_PATH)
	print(ach[-1].title)



def main():

	# First, get the signed p8 token
	token = create_signed_jwt(P8_APPLE_API_KEY_PATH)

	request_headers = {
		"Authorization": f"Bearer {token}"
	}

	# Now, read the achievements CSV
	achievements = get_achievements(ACHIEVEMENTS_CSV_PATH)

	# Now, get the game center ID
	game_center_detail_id = get_gc_detail_id(request_headers)
	if game_center_detail_id == None:
		return

	# Now, take each of the achievements and add to GC
	for (index, achievement) in enumerate(achievements, start=1):  # The item starts at index 1

		# For every 10 achievements, create a new signed token.
		# Otherwise it will just hang up
		if index % 10 == 0:
			# refresh the request headers
			new_token = create_signed_jwt(P8_APPLE_API_KEY_PATH)
			request_headers = {
				"Authorization": f"Bearer {new_token}"
			}

		# First, add it to GC
		achievement_id = create_achievement(achievement, game_center_detail_id, request_headers)
		if achievement_id == None:
			continue  # An error will have happened, which was printed and saved to disk.
			# Continue so we don't keep seiding more requests that will fail because this was None.

		for (dest_lang, dest_locale) in DESTINATION_LANGUAGES:

			# Now, create a localization (containing the descriptions and image)
			localization_id = create_localization(dest_locale, achievement.translated(dest_lang), achievement_id, request_headers)
			if localization_id == None:
				continue

			# Now, add an image to it
			add_image(achievement, ACHIEVEMENT_IMAGE_ROOT_PATH, localization_id, request_headers)

	# Now save the errors list to disk IF we need to
	if len(errors) > 0:
		with open("gk_achievements_upload_errors.txt", "w") as error_file:
			error_file.write("\n\n".join(errors))
			print("Saved errors to gk_achievements_upload_errors.txt file.")



if __name__ == "__main__":

	# main()
	test()


