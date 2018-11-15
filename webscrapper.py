from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup
import json
import os
import csv
import numpy as np
def simple_get(url, params=(), headers={}):
	"""
	Attempts to get the content at `url` by making an HTTP GET request.
	If the content-type of response is some kind of HTML/XML, return the
	text content, otherwise return None.

	:param params: GET request parameters 
	"""
	try:
		resp = get(url, params=params, headers=headers)
		if check_status_code(resp):
			return resp
		else:
			return None

	except RequestException as e:
	    print('Error during requests to {0} : {1}'.format(url, str(e)))
	    return None


def check_status_code(resp):
	"""
	Checks if resposne given was successful

	:param resp: request.get object
	"""
	code = resp.status_code
	print(code)
	if code == 200:
		return True
	else:
		return False


def get_keyword_phrase_set(topic, adjectives):
	"""
	Takes a keyword and a list of adjectives and generates a list of phrases

	:param topic: STRING representing topical item such as leggings
	:param adjectives: LIST of adjectives describing topical item such as nike
	:return: LIST of phrases
	"""
	phrase_set = ["womens pockets {0} {1}".format(adjective, topic) for adjective in adjectives]
	return phrase_set


def get_parsed_html_for_phrase(phrase):
	"""
	Gets html for a given search phrase

	:param phrase: STRING representing a typical search bar phrase on amazon
	:return: html for that url generated page
	"""
	headers = {'User-Agent': 'Mozilla/5.0'}
	base_url = 'https://www.amazon.com/s/ref=nb_sb_noss_2'
	params = (
		('url', 'search-alias'),
		('field-keywords', phrase),
	)
	raw_html = simple_get(base_url, params, headers).content
	return BeautifulSoup(raw_html, 'lxml')


def price_parser(price_soup):
	"""
	Receives a price soup object which should be a span tag
	of the class 'sx-price' and returns the actual price

	:param price_soup: bs4 SOUP object for the price of some item
	:return: NUMBER indicating the price of the soup object
	"""
	whole = price_soup.find('span', {'class':'sx-price-whole'})
	fractional = price_soup.find('sup', {'class':'sx-price-fractional'})
	currency = price_soup.find('sup', {'class':'sx-price-currency'})
	price = currency.getText() + whole.getText() + '.' + fractional.getText()
	return price


def image_parser(image_soup):
	"""
	Receives a image soup object which should be a img tag
	of the classes 's-access-image cfMarker' and returns the img url

	:param image_soup: bs4 SOUP object for the image of some item
	:return: STRING indicating the image url
	"""
	return image_soup['src']


def rating_parser(rating_soup, getText=True):
	"""
	Receives a rating soup object which should be a span tag
	of the class 'a-icon-alt' and returns a numerical value between
	0 and 10

	:param rating_soup: bs4 SOUP object for the rating of some item
	:return: NUMBER indicating the rating of the soup object
	"""
	for rating in rating_soup:
		text = rating.getText()
		if text != 'Prime':
			if getText: # will get 4.5 out of 5
				return text
			else: # will get 4.5
				return text.split()[0]
	return None


def title_parser(title_soup):
	"""
	Receives a title soup object which should be a h2 tag
	of the classes 'a-size-medium s-inline  s-access-title  a-text-normal'
	and returns a STRING object of that items title

	:param rating_soup: bs4 SOUP object for the title of some item
	:return: STRING indicating the title/header of the soup object
	"""
	text = title_soup.getText()
	text = text.replace('[Sponsored]', '')
	return text


def parse_item(item):
	"""
	Receives a soup item and parses the item in a format that is
	easily readable. Essentially, we are extracting only the information
	we want from some soup_item

	:param item: bs4 SOUP object
	:return: DICT of the form 
		{'price':NUMBER, 'image':STRING(url), 'rating':NUMBER, 'title':STRING}
	"""
	parsed_item = {}

	# Get item's price and return fractional value of said price
	price_soup = item.find('span', {'class':'sx-price'})
	price = price_parser(price_soup)
	parsed_item['price'] = price

	# Get item's image and return that url
	image_soup = item.find('img', {'class': 's-access-image cfMarker'})
	image = image_parser(image_soup)
	parsed_item['image'] = image

	# Get item's rating and return that numeric value out of 5
	rating_soup = item.findAll('span', {'class': 'a-icon-alt'})
	rating = rating_parser(rating_soup)
	parsed_item['rating'] = rating

	# Get item's title and return that string
	title_soup = item.find('h2', {'class': 'a-size-base s-inline s-access-title a-text-normal'})
	title = title_parser(title_soup)
	parsed_item['title'] = title

	return parsed_item


def page_crawler(parsed_page, adjective, keyword, num_entries=10):
	"""
	Parses and returns images from some given amazon page based on adjectives,
	and keywords

	:param parsed_page: bs4 SOUP object of some amazon web page
	:param adjective: STRING used in file saving convention
	:param keyword: STRING used in file saving convention
	:param num_entries: NUMBER of entries to save and return
	:return: DICT, e.g. {id:{'price':..., 'image':..., 'rating':..., 'title':...}, ...}
	"""

	# Temporarily locally saving data 
	pathname = keyword + "/" + adjective + ".txt"
	if not os.path.exists(keyword):
	    os.makedirs(keyword)

    # Grab list of returned items
	unordered_list_results = parsed_page.find('ul', {'id':'s-results-list-atf'})
	# Grab individual items from ul list and cast to list
	list_items = unordered_list_results.findChildren('li', recursive=False)

	# Return dictionary
	# {id:{'price':..., 'image':..., 'rating':..., 'title':...}, ...}
	ret = [parse_item(item) for item in list_items]
	return ret


def writetocsv(filename, data, mode='w'):
	"""
	Writes some input data consisting of a 1d list of dictionaries to csv file

	:param filename: STRING indicating csv filename
	:param data: 1d numpy array of dictionaries representing objects to be stored
	:param mode: char representing the mode in which we open the file with
	"""
	data = data.flatten()
	with open(filename, mode) as file:
		w = csv.DictWriter(file, data[0].keys())
		w.writeheader()
		for obj in data:
			w.writerow(obj)


def scrapper():
	"""
	Scraps Amazon for every noun, list of adjectives pair in tags.txt
	"""
	try:
		with open('./tags.txt', 'r') as file:
			data = eval(file.read())
			csv_data = []
			for noun in data:
				adjectives = data[noun]
				phrases_array = get_keyword_phrase_set(noun, adjectives)
				html_pages = [get_parsed_html_for_phrase(phrase) for phrase in phrases_array]
				csv_sub_data = [page_crawler(html_pages[i], adjectives[i], noun) for i in range(len(html_pages))]
				
				csv_data += csv_sub_data
			csv_data = np.array(csv_data)
			writetocsv('./scraper-dump.csv', csv_data)
			
		return
	except KeyError as e:
		print('Found Invalid Keyword Found in tags.txt: {0}'.format(e))
		return
	except FileNotFoundError as f:
		print('tags.txt not found: {0}'.format(f))
		return


if __name__ == '__main__':
	scrapper()
