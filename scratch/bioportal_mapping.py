import urllib.request, urllib.error, urllib.parse
import json

REST_URL = "http://data.bioontology.org"
API_KEY = "2180821f-1890-4533-a890-2b16836d44f8"

mapping_dict = {}

def get_json(url):
    opener = urllib.request.build_opener()
    opener.addheaders = [('Authorization', 'apikey token=' + API_KEY)]
    return json.loads(opener.open(url).read())

if __name__ == '__main__':
    meddra_code = ['10003988']
    
    for code in meddra_code:
        url = "/ontologies/MEDDRA/classes/http%3A%2F%2Fpurl.bioontology.org%2Fontology%2FMEDDRA%2F"+code+"/mappings"
        mappings = get_json(REST_URL+url)
        print('Number of mappings = '+str(len(mappings)))
        for item in mappings:
            classes = item['classes'][1]
            if 'ontology' in classes['links']:
                ontology_full = classes['links']['ontology'] 
                ontology_short = ontology_full.split('/')[-1]
                if ontology_short == 'HP' or ontology_short == 'MONDO':
                    if 'self' in classes['links']:
                        ontology_uri = classes['links']['self']
                        obo_code = ontology_uri.split('%2F')[-1]
                        mapping_dict[code] = obo_code

    print(mapping_dict)
    #save as pickle or text or TSV

        