from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup
import json
import os
import csv
import numpy as np
from multiprocessing import Pool
from fake_useragent import UserAgent
from urllib.request import Request, urlopen
import random
def get_proxy_list():
	proxies = []
	ua = UserAgent()
	# Retrieve latest proxies
	# url = 'https://www.sslproxies.org/'
	# headers = {'User-Agent': ua.random}
	# proxies_req = get(url, headers=headers)

	# Retrieve latest proxies
	proxies_req = Request('https://www.sslproxies.org/')
	proxies_req.add_header('User-Agent', ua.random)
	proxies_doc = urlopen(proxies_req).read().decode('utf8')

	soup = BeautifulSoup(proxies_doc, 'html.parser')
	proxies_table = soup.find(id='proxylisttable')

	for row in proxies_table.tbody.find_all('tr'):
		# Must cast rows to python strings otherwise multiprocessing pool
		# Will fail due to handling bs4 element string objects
		proxies.append({
			'ip':   str(row.find_all('td')[0].string),
			'port': str(row.find_all('td')[1].string)
		})
	return proxies


def simple_get(url, params=(), headers={}, proxy={}):
	"""
	Attempts to get the content at `url` by making an HTTP GET request.
	If the content-type of response is some kind of HTML/XML, return the
	text content, otherwise return None.

	:param params: GET request parameters 
	"""
	try:
		resp = get(url, params=params, headers=headers)
		if check_status_code(resp):
			# Check for captcha 
			if (BeautifulSoup(resp.content, 'lxml').find('p', {'class':'a-last'})) == None:
				print(resp.status_code)
				return resp

	except RequestException as e:
	    print('Error during requests to {0} : {1}'.format(url, str(e)))
	    return None
	return None


def check_status_code(resp):
	"""
	Checks if resposne given was successful

	:param resp: request.get object
	"""
	code = resp.status_code
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


def get_parsed_html_for_phrase(phrase, proxy_list):
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
	proxy = proxy_list[random.randint(0, len(proxy_list)-1)]
	raw_html = simple_get(base_url, params, headers, proxy)
	while (raw_html == None):
		index = random.randint(0, len(proxy_list)-1)
		proxy = proxy_list[index]
		print("Proxy doesn't work proxy: {0}\n".format(proxy[index]))
		raw_html = simple_get(base_url, params, headers, proxy[index])
	return BeautifulSoup(raw_html.content, 'lxml')


def price_parser(price_soup):
	"""
	Receives a price soup object which should be a span tag
	of the class 'sx-price' and returns the actual price

	:param price_soup: bs4 SOUP object for the price of some item
	:return: NUMBER indicating the price of the soup object
	"""
	if price_soup == None:
		return None
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
	if image_soup == None:
		return None
	return image_soup['src']


def rating_parser(rating_soup, getText=True):
	"""
	Receives a rating soup object which should be a span tag
	of the class 'a-icon-alt' and returns a numerical value between
	0 and 10

	:param rating_soup: bs4 SOUP object for the rating of some item
	:return: NUMBER indicating the rating of the soup object
	"""
	if rating_soup == None:
		return None
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
	if title_soup == None:
		return None
	text = title_soup.getText()
	text = text.replace('[Sponsored]', '')
	return text


def href_parser(href_soup):
	"""
	Receives an anchor tag soup object and returns the appropriate href
	link.

	:param href_soup: soup object for some anchor tag
	:return: url of href
	"""
	if href_soup == None:
		return None
	if href_soup['href'][:3] == '/gp':
		return 'www.amazon.com' + href_soup['href']
	return href_soup['href']


def parse_item(item):
	"""
	Receives a soup item and parses the item in a format that is
	easily readable. Essentially, we are extracting only the information
	we want from some soup_item

	:param item: bs4 SOUP object
	:return: DICT of the form 
		{'price':NUMBER, 'image':STRING(url), 
		'rating':NUMBER, 'title':STRING,
		'href': STRING}
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

	href_soup = item.find('a', {'class': 'a-link-normal a-text-normal'})
	href = href_parser(href_soup)
	parsed_item['href'] = href

	return parsed_item


def page_crawler(parsed_page, adjective, noun):
	"""
	Parses and returns images from some given amazon page based on adjectives,
	and keywords

	:param parsed_page: bs4 SOUP object of some amazon web page
	:param adjective: STRING used in file saving convention
	:param noun: STRING used in file saving convention
	:return: DICT, e.g. {id:{'price':..., 'image':..., 'rating':..., 'title':...}, ...}
	"""
	# Temporarily locally saving data 
	root = os.path.join('./data', noun)
	if adjective == '':
		filename = os.path.join(root, noun+'.csv')
	else:
		filename = os.path.join(root, adjective + '.csv')

	if not os.path.exists(root):
	    os.makedirs(root)
	# Grab list of returned items

	results = parsed_page.findAll('ul', {'class':'s-result-list'})
	data = []
	for result in results:
		# Grab individual items from ul list and cast to list
		if result == None: # If only atf list was returned
			continue
		list_items = result.findChildren('li', recursive=False)
		# Return dictionary
		# [{'price':..., 'image':..., 'rating':..., 'title':..., 'href':...}, ...]
		data += [parse_item(item) for item in list_items]

	data = np.array(data).flatten()
	with open(filename, 'w') as csv_file:
		w = csv.DictWriter(csv_file, data[0].keys())
		w.writeheader()
		for row in data:
			# Sanitization TODO, dresses key word but dress found discards dress
			if noun in str(row['title']).lower():
				w.writerow(row)
		print('wrote to {0}'.format(filename))


def process_func(noun, adjectives, proxy_list):
	phrases_array = get_keyword_phrase_set(noun, adjectives)
	html_pages = [get_parsed_html_for_phrase(phrase, proxy_list) for phrase in phrases_array]
	for i in range(len(html_pages)):
		page_crawler(html_pages[i], adjectives[i], noun)


def scrapper(proxies={}):
	"""
	Scraps Amazon for every noun, list of adjectives pair in tags.txt
	"""
	try:
		with open('./tags.txt', 'r') as file:
			data = eval(file.read())
			nouns = [noun for noun in data]
			adjectives_list = [data[noun] for noun in nouns]
			proxies_arg = [proxies]*len(nouns)
			args = zip(nouns, adjectives_list, proxies_arg)

			pool = Pool()
			pool.starmap(process_func, args)
			pool.close()
			pool.join()
		return
	except KeyError as e:
		print('Found Invalid Keyword Found in tags.txt: {0}'.format(e))
		return
	except FileNotFoundError as f:
		print('FileNotFoundError: {0}'.format(f))
		return


def search_results(phrase):
	"""
	Parses some phrase to determine nouns and adjectives
	and returns appropriate data. Returns valid information

	
	:param phrase: STRING of some search query
	:returns: array of dictionaries where the key filepath
		is the local path for a csvfile and the key header is
		the header to be used on a search page. Smaller indices
		show more relevant search options opposed to larger
		indices
	"""
	if not os.path.exists('data'):
		print('data path nonexistent')
		return []

	# Turn into list
	if type(phrase) == str:
		phrase = phrase.lower().split()

	noun = ''
	# Is there a noun in the search query
	nouns = os.listdir('data')
	for word in phrase:
		if word in nouns:
			noun = word
			break

	if noun == '':
		# TODO: return adjectives only
		return []

	noun_foldername = os.path.join('data', noun)
	csv_files = os.listdir(noun_foldername)
	num_files = len(csv_files)
	files = [{}] * num_files
	k = 0
	j = -1
	# Iterate through csv_files
	for i in range(num_files):
		# Create Paths
		filename = csv_files[i]
		csv_adjective = filename[:-4]
		adjective_path = os.path.join(noun_foldername, csv_adjective)
		file = adjective_path + '.csv'
		img = ''
		f = open(file, 'r')

		reader = csv.DictReader(f)
		for row in reader:
			img = row['image']
			break
		f.close()

		if csv_adjective in phrase:
			if (csv_adjective != noun):
				# Add relevant search to front
				files[k] = {
					'filepath':adjective_path, 
					'header':csv_adjective + ' ' + noun,
					'topic':csv_adjective + '-' + noun,
					'image':img
				}
			else:
				files[k] = {
					'filepath':adjective_path, 
					'header':csv_adjective,
					'topic':csv_adjective + '-' + noun,
					'image':img

				}
			k += 1
		else:
			if (csv_adjective != noun):

				# Add less relevant search to back
				files[j] = {
					'filepath':adjective_path, 
					'header':csv_adjective + ' ' + noun,
					'topic':csv_adjective + '-' + noun,
					'image':img

				}
			else:
				files[j] = {
					'filepath':adjective_path, 
					'header':csv_adjective,
					'topic':csv_adjective + '-' + noun,
					'image':img
				}
			j -= 1
	return files


def get_page_data(noun, adjective):
	"""
	Gets page data based on a noun and adjective searched

	:param noun: STRING of some noun
	:param adjective: STRING of some adjective
	:return: csv.DictReader iterable object if webscrapper has data
		for given inputs, None otherwise
	"""
	filename = './data/' + noun + '/' + adjective + '.csv'
	if os.path.exists(filename):
		ret = []
		with open(filename, 'r') as csv_file:
			reader = csv.DictReader(csv_file)
			for row in reader:
				ret += [dict(row)]
		return ret
	else:
		return None

if __name__ == '__main__':
	proxies = get_proxy_list()
	scrapper(proxies=proxies)
