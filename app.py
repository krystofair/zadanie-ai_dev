import requests as rq
from flask import Flask, request
from flask.json import jsonify
import logging

app = Flask("ai_devs")
log = logging.getLogger("ai_devs")
log.setLevel(logging.DEBUG)
log.info = print
log.debug = print
log.warning = print

"""
Kto wchodzi w skład, na jakiej uczelni działają i kto ich sponsoruje.
Trzy zbiory danych w których można wyszukiwać, ale tylko dwa toole hehe ;)
"""
DATA_URL = "https://letsplay.ag3nts.org/data"


def load_uczelnie():
    response = rq.get(DATA_URL + '/uczelnie.json')
    log.info("loaded uczelnie")
    return response.json()

def load_osoby():
    response = rq.get(DATA_URL + '/osoby.json')
    log.info("loaded osoby")
    return response.json()

def load_badania():
    response = rq.get(DATA_URL + '/badania.json')
    log.info("loaded badania")
    return response.json()

# Second tool interface

def search_sponsor(nazwa_badania, uczelnia, badania):
    b2s = dict([ (b['nazwa'], b['sponsor']) for b in badania if b['uczelnia'] == uczelnia ] )
    return b2s.get(nazwa_badania, "Nie znaleziono sponsora")

def search_persons(uczelnia, osoby):
    persons = []  # "{imie} {nazwisko}"
    for osoba in osoby:
        if osoba['uczelnia'].upper() == uczelnia.upper():
            persons.append(' '.join([osoba['imie'], osoba['nazwisko']]))
    return ', '.join(persons)

def name_of_university(uczelnia, uczelnie):
    for u in uczelnie:
        if uczelnia.upper() == u['id']:
            return f"{u['nazwa']} w {u['miasto']}"
    return "Nie znaleziono uczelni"

def _remove_stop_words(tokens):
    return [t for t in tokens
                  if t not in ['na', 'w', 'o', 'i', 'albo', 'lub', 'oraz', 'czyli']]

# First tool interface / class

class Correlation:
    """Buduje graf z nazw badania jako wyraz -> uczelnia
    Wg grafu oblicza ile wyrazów odpytanych przez agenta jest pod jakąś uczelnią,
    im więcej wyrazów się zgodzi tym większe prawdopodobieństwo że uczelnia realizuje
    takie badanie."""

    def __init__(self):
        self.graph: dict[str, list[str]] = dict()
        self.researches = dict()
        self._builded = False

    def build_graph(self, badania: list[dict]):
        if self._builded:
            return
        for badanie in badania:
            tokens = badanie['nazwa'].split(' ')
            for token in _remove_stop_words(tokens):
                log.debug(token)
                if token in self.graph:
                    self.graph[token].append( badanie['uczelnia'] )
                    self.researches[token].append( badanie['nazwa'] )
                else:
                    self.graph[token] = [ badanie['uczelnia'] ]
                    self.researches[token] = [ badanie['nazwa']  ]
            log.debug(self.graph.items())
        self._builded = True

    def get_best_matches(self, nazwa_badania_agent_ask):
        U = dict()
        B = dict()
        tokens = nazwa_badania_agent_ask.split(' ')
        for token in _remove_stop_words(tokens):
            ids = self.graph.get(token, [])
            names = self.researches.get(token, [])
            for uczelnia_id, name in zip(ids, names):
                log.info(uczelnia_id, name)
                if uczelnia_id:
                    U[uczelnia_id] = 1 if uczelnia_id not in U else U[uczelnia_id] + 1
                if name:
                    B[name] = 1 if name not in B else B[name] + 1
        U_mod = dict( (v, k) for k, v in U.items() )
        B_mod = dict( (v, k) for k, v in B.items() )
        try:
            U_key = sorted(U_mod)[-1]
            B_key = sorted(B_mod)[-1]
        except IndexError:
            return ""
        return U_mod[U_key], B_mod[B_key]
  
# API

@app.route('/tool2', methods=['POST'])
def get_information():
    input_json = request.get_json()
    log.info("[->] {}".format(input_json))
    if 'test' in input_json.get('input', 'abrakadabra k.'):
        return { "output": input_json['input'] }
    dane = input_json.get('input')
    try:
        uczelnia, nazwa_badania = dane.split('|')
    except:
        return { "output": "Zbyt dużo/mało argumentów" }
    sponsor = search_sponsor(nazwa_badania, uczelnia, BADANIA)
    osoby = search_persons(uczelnia, OSOBY)
    uczelnia_stmt = name_of_university(uczelnia, UCZELNIE)
    return {
            "output": f"{osoby} {uczelnia_stmt},sponsor: {sponsor}"
    }


@app.route("/tool1", methods=['POST'])
def check_badanie():
    input_json = request.get_json()
    log.info("[->] {}".format(input_json))
    if 'test' in input_json.get('input', 'abrakadabra k.'):
        return { "output": input_json['input'] }

    badanie_do_sprawdzenia = input_json.get('input')

    uczelnia, badanie = corr.get_best_matches(badanie_do_sprawdzenia)
    log.info(uczelnia, badanie)
    return { "output": f"{uczelnia}|{badanie}" }

UCZELNIE = load_uczelnie()
OSOBY = load_osoby()
BADANIA = load_badania()

corr = Correlation()
corr.build_graph(BADANIA)

if __name__ == '__main__':
    app.run(debug=False)
