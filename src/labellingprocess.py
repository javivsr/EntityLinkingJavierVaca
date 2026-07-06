import requests
import json
import pandas as pd
import matplotlib.pyplot as plt
import re
import os
from rapidfuzz import fuzz
from time import sleep
from pathlib import Path
from random import random
from math import isnan
from collections import Counter
from IPython.display import display

PROGRESS_CPC = "data/cpc_progress.json"
FILE_CPC_ALL = "data/cpc_records.jsonl"
FILE_CPC_EXTRACT = "data/labelling/cpc_extract.jsonl"
FILE_STEP1 = "data/labelling/step1.csv"
FILE_STEP2a = "data/labelling/step2a.csv"
FILE_STEP2b = "data/labelling/step2b.csv"
FILE_STEP3 = "data/labelling/step3.csv"
FILE_LABELLING = "data/labelling/labelling.csv"

CPC_DATABASE_URL = "http://dati.acs.beniculturali.it/solr.CPC/select"
WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = { "User-Agent": "CPC-Entity-Linking-Project/2.0 (javiervaca437@gmail.com)" }

# Ajustes
BATCH_SIZE = 1000
SLEEP_SECONDS = 0.4
TIMEOUT = 60

def get_total(session):
    params = {
        "q": "*:*",
        "rows": 0,
        "wt": "json"
    }
    r = session.get(CPC_DATABASE_URL, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data["response"]["numFound"]


def fetch_batch(session, start, rows):
    params = {
        "q": "*:*",
        "start": start,
        "rows": rows,
        "wt": "json"
    }
    r = session.get(CPC_DATABASE_URL, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data["response"]["docs"]


def load_progress(fich):
    if not os.path.exists(fich):
        return {"next_start": 0}
    with open(fich, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(fich, next_start, total):
    tmp_file = fich + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump({
            "next_start": next_start,
            "total": total,
            "updated_at_epoch": time.time()
        }, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, fich)


def ensure_output_exists(fich):
    Path(fich).touch(exist_ok=True)


def download_cpc(fich_cpc, fich_progress):
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        total = get_total(session)
    except Exception as e:
        print(f"Error obteniendo numFound: {e}", file=sys.stderr)
        return

    progress = load_progress(fich_progress)
    start = int(progress.get("next_start", 0))

    if start < 0 or start > total:
        print(f"Valor de progreso inválido: {start}", file=sys.stderr)
        return

    ensure_output_exists(fich_cpc)

    print(f"Total de registros: {total}")
    print(f"Reanudando desde: {start}")
    print(f"Lote: {BATCH_SIZE}")

    written = 0

    with open(fich_cpc, "a", encoding="utf-8") as out:
        while start < total:
            retries = 3
            docs = None

            for attempt in range(1, retries + 1):
                try:
                    docs = fetch_batch(session, start, BATCH_SIZE)
                    break
                except requests.RequestException as e:
                    print(f"[WARN] Error en start={start}, intento {attempt}/{retries}: {e}")
                    if attempt == retries:
                        print("[ERROR] Se agotaron los reintentos.")
                        save_progress(fich_progress, start, total)
                        sys.exit(2)
                    time.sleep(2 * attempt)

            if not docs:
                print(f"[INFO] Sin documentos en start={start}. Fin anticipado.")
                save_progress(fich_progress, start, total)
                break

            for doc in docs:
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")

            out.flush()
            os.fsync(out.fileno())

            start += len(docs)
            written += len(docs)

            save_progress(fich_progress, start, total)
            print(f"Descargados {start}/{total} (+{len(docs)} en este lote)")

            time.sleep(SLEEP_SECONDS)

    print(f"Terminado. Registros añadidos en esta ejecución: {written}")
    print(f"Archivo de salida: {fich_cpc}")
    print(f"Progreso guardado en: {fich_progress}")

def valores(dat, campo):
    c = Counter(x for d in dat if campo in d for x in d[campo])
    return (len(dat)-sum(c[k] for k in c), c)

def cpc_analysis(file):
    dat = [json.loads(lin.strip()) for lin in open(file, encoding='utf-8')]
    print(f"Número de registros: {len(dat)}")
    campos = set().union(*(d.keys() for d in dat))
    n = len(dat)
    df = pd.DataFrame(columns=["Field","Null_Ratio","Num_Distinct_Values","Most_Common","Most_Common_Ratio"])
    handle = display(df, display_id=True)
    for campo in sorted(campos):
        (m,c) = valores(dat, campo)
        (kmc,nmc) = c.most_common(1)[0]
        df.loc[len(df)] = {"Field":campo, "Null_Ratio":m/n, "Num_Distinct_Values": len(c), "Most_Common":kmc, "Most_Common_Ratio":nmc/n}
        handle.update(df)

def add_subset(fich_cpc, fich_cpc_extract, p):
    # Creamos el fichero si no existe
    Path(fich_cpc_extract).touch(exist_ok=True)
    # Leemos el fichero
    with open(fich_cpc_extract,'a',encoding='utf-8') as fo:
        fo.writelines(lin for lin in open(fich_cpc,'r',encoding='utf-8') if random() < p)

def unpack(val):
    return val['value'] if isinstance(val, dict) else val

def buscar(query, language, limit):
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": language,
        "format": "json",
        "limit": limit,
        "type": "item"
    }
    for intento in range(5):
        response = requests.get(WIKIDATA_SEARCH_URL, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 429:
            espera = int(response.headers.get("Retry-After", 2**intento))
            print(f"429 recibido, esperando {espera}s (intento {intento})")
            sleep(espera)
            continue
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("search", []):
            results.append({
                "qid": item.get("id", ""),
                "label": item.get("label", ""),
                "description": unpack(item.get("description", "")),            
                "aliases": [unpack(a) for a in item.get("aliases", [])],
                "lang": language
            })
        return results
    raise RuntimeError(f"Error de descarga!")

def enum_query(reg):
    cnom = reg['COGNOME'][0].strip(' \"')
    if 'NOME' in reg:
        # Caso especial: Si COGNOME es Del, entonces NOME tiene la forma "Apellido Nombre" y hay que transformar como "Nombre Del Apellido"
        if cnom in ['Del','De','Di','Della','La']:
            vnom = reg['NOME'][0].strip(' \"').split(' ')
            if len(vnom) >= 2:
                yield (vnom[-1] + ' ' + cnom + ' ' + ' '.join(vnom[0:-1]), False)
        else:        
            nom = reg['NOME'][0].strip(' \"')
            yield (nom + ' ' + cnom, True)
            if ' ' in nom:            
                for nomp in nom.split(' '):
                    yield (nomp + ' ' + cnom, False)
    else:
        yield (cnom, True)

def step1b(fich_cpc, fich_fase1):
    if os.path.isfile(fich_fase1):
        df = pd.read_csv(fich_fase1, sep=';', encoding='utf-8')
    else:
        df = pd.DataFrame(columns=["cpc_id","query","variant","qid","label","description","aliases","lang"])
    dat_cpc = [json.loads(lin.strip(' \"')) for lin in open(fich_cpc,'r',encoding='utf-8')]
    existentes = set(df['cpc_id'])
    handle = display(df, display_id=True)
    try:
        for reg_cpc in dat_cpc:
            if reg_cpc['id'][0] in existentes:
                continue
            for (query, fst) in enum_query(reg_cpc):
                fil = {'cpc_id': reg_cpc['id'][0], 'query': query, 'variant': 'no' if fst else 'yes'}
                sleep(0.5)
                lri = buscar(query, 'it', 20)
                if not lri:
                    df.loc[len(df)] = fil
                    handle.update(df)
                else:
                    for ri in lri:
                        ri.update(fil)
                        df.loc[len(df)] = ri
                        handle.update(df)
    finally:
        df.to_csv(fich_fase1, sep=';', index=False, encoding='utf-8')

def parse_year(txt):
    if not txt:
        return 0
    match = re.search(r"(1[0-9]{3}|20[0-9]{2})", str(txt))
    if match:
        return int(match.group(1))
    return 0

SPARQL_FIELDS = [
    ('itemLabel', False),
    ('itemDescription', False),
    ('itemTypeLabel', False),
    ('birthDateLabel', False),
    ('birthPlaceLabel', True),
    ('occupationLabel', True),
    ('fatherNameLabel', True),
    ('nameLabel', True),
    ('surnameLabel', True),
    ('sexLabel', False),
    ('countryLabel', True)
]

def enriquece(reg_f1, dic_cpc):
    """
    Fetch lightweight structured details from Wikidata SPARQL.
    """
    qid = reg_f1['qid']
    query = f"""
    SELECT ?item ?itemLabel ?itemDescription ?itemTypeLabel ?birthDateLabel ?birthPlaceLabel
           ?occupationLabel ?fatherNameLabel ?nameLabel ?surnameLabel ?sexLabel ?countryLabel WHERE {{
      VALUES ?item {{ wd:{qid} }}
      OPTIONAL {{ ?item wdt:P31 ?itemType. }}
      OPTIONAL {{ ?item wdt:P569 ?birthDate. }}
      OPTIONAL {{ ?item wdt:P19 ?birthPlace. }}
      OPTIONAL {{ ?item wdt:P106 ?occupation. }}
      OPTIONAL {{ ?item wdt:P22/wdt:P735 ?fatherName. }}
      OPTIONAL {{ ?item wdt:P735 ?name. }}
      OPTIONAL {{ ?item wdt:P734 ?surname. }}
      OPTIONAL {{ ?item wdt:P21 ?sex. }}
      OPTIONAL {{ ?item wdt:P27 ?country. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "it,it,en". }}
    }}
    """
    params = {"query": query, "format": "json"}
    response = requests.get(WIKIDATA_SPARQL_URL, params=params, headers=HEADERS, timeout=60)
    response.raise_for_status()
    data = response.json()
    bindings = data.get("results", {}).get("bindings", [])
    wiki = dict([(k,set()) if fl else (k,"") for (k,fl) in SPARQL_FIELDS])
    wiki['qid'] = qid
    if bindings:
        for row in bindings:
            for (campo, fl) in SPARQL_FIELDS:
                if campo in row:
                    if fl:
                        wiki[campo].add(unpack(row[campo]))
                    else:
                        wiki[campo] = unpack(row[campo])
    cpc = dic_cpc[reg_f1['cpc_id']]
    res = {}
    res['cpc'] = reg_f1['cpc_id']
    res['qid'] = reg_f1['qid']
    res['tipo'] = wiki['itemTypeLabel']
    res['nom1'] = reg_f1['query']
    res['nom2'] = wiki['itemLabel']
    res['nac1'] = int(cpc.get('DATA_NASCITA',['-1000'])[0])
    res['nac2'] = parse_year(wiki.get('birthDateLabel', None))
    res['sex1'] = cpc['SESSO'][0]
    res['sex2'] = wiki.get('sexLabel',[""])[0:1]
    res['pais1'] = cpc.get('NAZIONE_DI_NASCITA',[""])[0]
    res['pais2'] = '|'.join(wiki['countryLabel'])
    res['ciudad1'] = cpc.get('COMUNE_DI_NASCITA',[""])[0]
    res['ciudad2'] = '|'.join(wiki['birthPlaceLabel'])
    res['oficio1'] = '|'.join(sorted(cpc.get('MESTIERE',[])))
    res['oficio2'] = '|'.join(sorted(wiki['occupationLabel']))
    res['padre1'] = cpc.get('PATERNITA',[""])[0]
    res['padre2'] = '|'.join(wiki['fatherNameLabel'])
    res['afil1'] = '|'.join(sorted(cpc.get('COLORE',[])))
    res['afil2'] = wiki.get('itemDescription',"")
    return res

def step2a(fich_cpc, fich_fase1, fich_fase2):
    dat_cpc = [json.loads(lin.strip(' \"')) for lin in open(fich_cpc,'r',encoding='utf-8')]
    dic_cpc = {r['id'][0]:r for r in dat_cpc}
    dfi = pd.read_csv(fich_fase1, sep=';', encoding='utf-8')
    fase1 = dfi[dfi['qid'].notnull()].to_dict('records')
    print(len(fase1))
    if os.path.isfile(fich_fase2):
        df2 = pd.read_csv(fich_fase2, sep=';', encoding='utf-8')
    else:
        df2 = pd.DataFrame(columns=['cpc','qid','tipo','nom1','nom2','nac1','nac2','sex1','sex2','pais1','pais2','ciudad1','ciudad2','oficio1','oficio2','padre1','padre2','afil1','afil2'])
    existentes = set(df2['cpc']+df2['qid'])
    handle = display(df, display_id=True)
    try:
        for reg in fase1:
            if reg['cpc_id']+reg['qid'] in existentes:
                continue
            sleep(0.5)
            df2.loc[len(df2)] = enriquece(reg, dic_cpc)
            handle.update(df2)
    finally:
        df2.to_csv(fich_fase2, sep=';', index=False, encoding='utf-8')

def step2b(fich_fase1, fich_fase2, fich_fase3):
    df1 = pd.read_csv(fich_fase1, sep=';', encoding='utf-8')
    df2 = pd.read_csv(fich_fase2, sep=';', encoding='utf-8')
    num_ent = Counter(r['cpc_id'] for r in df1.to_dict('records'))
    fase1 = df1[df1['qid'].notnull()].to_dict('records')
    dic_ali = {r['cpc_id']+r['qid']:r['aliases'][1:-1].strip(" \'") for r in fase1}
    df2['num_ent'] = df2.apply(lambda fil: num_ent[fil.cpc], axis = 1)
    df2['alias'] = df2.apply(lambda fil: dic_ali[fil.cpc+fil.qid], axis = 1)
    df2.to_csv(fich_fase3, sep=';', index=False, encoding='utf-8')

def normal(txt):
    txt = str(txt).strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')

def eval_birth(row):
    dif = abs(row.nac1-row.nac2)
    return -1 if dif > 1 else 1-dif

def eval_name(row):
    # Comprobación rápida (cierta en la mayoría de los casos)
    if row.nom1 == row.nom2 or row.nom1 == row.alias:
        return 1
    # Caso especial en que el nombre de la entrada contiene un segundo cognome
    if row.nom2.startswith(row.nom1) and row.nom2[len(row.nom1)] == ' ':
        return 1
    # Normalizamos y quitamos acentos    
    n1 = normal(row.nom1)
    return 1 if n1 == normal(row.nom2) or n1 == normal(row.alias) else -1

def eval_sex(row):
    if row.sex1 == row.sex2:
        return 1
    return 0 if isinstance(row.sex1, float) or isinstance(row.sex2, float) else -1

EXCEP_COUNTRY = {'Yugoslavia':'Jugoslavia', 'Repubblica San Marino':'San Marino'}

def eval_country(row):
    if isinstance(row.pais1, float) or isinstance(row.pais2, float):
        return 0
    if row.pais1 in row.pais2:
        return 1
    # Excepciones
    if row.pais1 in EXCEP_COUNTRY and EXCEP_COUNTRY[row.pais1] in row.pais2:
        return 1
    return -1

def eval_city(row):
    if isinstance(row.ciudad1, float) or isinstance(row.ciudad2, float):
        return 0
    # Comprobación normalizada
    if normal(row.ciudad1) == normal(row.ciudad2):
        return 1
    # Caso especial en que la ciudad de la entrada contiene información extra
    if row.ciudad2.startswith(row.ciudad1) and row.ciudad2[len(row.ciudad1)] == ' ':
        return 1
    # Caso
    return -1

def eval_city2(row):
    if isinstance(row.ciudad1, float) or isinstance(row.ciudad2, float):
        return 0
    return fuzz.partial_ratio(row.ciudad1, row.ciudad2)/100

def eval_father(row):
    if isinstance(row.padre1, float) or isinstance(row.padre2, float):
        return 0
    # Comprobación normalizada
    n1 = normal(row.padre1)
    n2 = normal(row.padre2)
    return 1 if n1 == n2 or n1 in n2 or n2 in n1 else -1

EQUIV_OCCUP = {
    'maestro' : 'professore',
    'maestra' : 'professore',
    'insegnante' : 'professore',
    'pedagogista' : 'professore',
    'giornalista pubblicista' : 'pubblicista',
    'deputato' : 'politico',
    'monsignore' : 'sacerdote',
    'giurista' : 'avvocato'
}

def normal_occup(txt):
    txt = txt.lower()
    if txt == 'dottore':
        txt = 'medico'
    txt = re.sub(" ex$","",txt)
    txt = re.sub(" in .*","",txt)
    txt = re.sub(" di .*","",txt)
    txt = re.sub(" universitario$"," ",txt)
    txt = re.sub(" elementare$"," ",txt)
    txt = re.sub(" cattolico$"," ",txt)
    txt = re.sub(" chirurgo$"," ",txt)
    txt = re.sub(" commercialista$"," ",txt)     
    txt = re.sub("(dato incerto)","",txt)
    txt = txt.strip()
    return EQUIV_OCCUP.get(txt, txt)

def extract_occupation(txt):
    return set(normal_occup(oc) for oc in txt.split('|'))

def eval_occupation(row):
    if isinstance(row.oficio1, float) or isinstance(row.oficio2, float):
        return 0
    set_occup1 = extract_occupation(row.oficio1)
    set_occup2 = extract_occupation(row.oficio2)
    return 1 if len(set_occup1 & set_occup2) > 0 else -1
    
def eval_affiliation(row):
    if isinstance(row.afil1, float) or isinstance(row.afil2, float):
        return 0
    return 1 if row.afil1 in row.afil2 else 0

def step3(fich_fase3, fich_fase4, fich_eval):
    df3 = pd.read_csv(fich_fase3, sep=';', encoding='utf-8')
    # Eliminamos directamente entradas que no sean de personas
    df4 = df3[df3['tipo']=='umano'].copy()
    df4.drop(columns=['tipo'], inplace=True)
    # Para año de nacimiento exigimos igualdad o diferencia de 1. Si no hay datos no concuerdan.
    df4['eval_birth'] = df4.apply(eval_birth, axis = 1)
    # Para nombre comprobamos igualdad (teniendo en cuenta caso y acentos), campo alias y casos especiales
    df4['eval_name'] = df4.apply(eval_name, axis = 1)
    # Para sexo comprobamos igualdad o ausencia de datos
    df4['eval_sex'] = df4.apply(eval_sex, axis = 1)
    # Para pais comprobamos igualdad, contenido en, excepciones
    df4['eval_country'] = df4.apply(eval_country, axis = 1)
    # Para ciudad comprobamos igualdad
    df4['eval_city'] = df4.apply(eval_city, axis = 1)
    # Para padre comprobamos igualdad y contencion
    df4['eval_father'] = df4.apply(eval_father, axis = 1)
    # Para oficio es más complicado
    df4['eval_occupation'] = df4.apply(eval_occupation, axis = 1)
    # Para afiliación solo comprobar si esta contenido en entrada
    df4['eval_affiliation'] = df4.apply(eval_affiliation, axis = 1)
    # Nuevo test para ciudad
    df4['eval_city2'] = df4.apply(eval_city2, axis = 1)
    df4.sort_values(by=['cpc','qid'], axis=0, inplace=True)
    df4.to_csv(fich_fase4, sep=';', encoding='utf-8', index=False)
    df4.insert(loc=0, column='gold', value="")
    df4[df4['eval_birth'] >= 0].to_csv(fich_eval, sep=';', encoding='utf-8', index=False)
    return df4

def group(dat, fkey, fval):
    res, lis_act, key_act = [], [], None
    for r in sorted(dat, key=fkey):
        key = fkey(r)
        val = fval(r)
        if key == key_act:
            if val:
                lis_act.append(fval(r))
        else:
            if key_act:
                res.append((key_act, lis_act))
            key_act = key
            lis_act = [val] if val else []
    res.append((key_act, lis_act))
    return res

def report(fich_fase1, fich_fase3, fich_eval):
    fase1 = pd.read_csv(fich_fase1, sep=';', encoding='utf-8').to_dict('records')
    grupos = group(fase1, lambda r: r['cpc_id'], lambda r: '' if isinstance(r['qid'], float) else r['qid'])
    print("FASE 1 - BÚSQUEDA DIRECTA EN WIKIDATA")
    print(f"Número de registros CPC analizados: {len(grupos)}")
    gfind = [len(lis) for (_,lis) in grupos if lis]
    print(f"{len(grupos)-len(gfind)} no encontrados, {len(gfind)} encontrados * {sum(gfind)/len(gfind):.2f} entradas promedio = {sum(gfind)} pares CPC-WKD.")
    print("\nFASE 2 - COMPLETAR REGISTROS MEDIANTE SPARQL - WIKIDATA")
    fase3 = pd.read_csv(fich_fase3, sep=';', encoding='utf-8').to_dict('records')
    fase3h = list(filter(lambda r: r['tipo'] == 'umano', fase3))
    fase3c = [r['cpc'] for r in fase3h if abs(r['nac1']-r['nac2']) <= 1]
    print(f"Filtro de ser humano: {len(fase3h)} pares CPC-WKD")
    print(f"Filtro de fecha de nacimiento: {len(fase3c)} pares CPC-KWD ({len(set(fase3c))} personas)")
    print("\nFASE 3 - ETIQUETADO MANUAL DE LOS PARES CPC-WKD")
    fase4 = pd.read_csv(fich_eval, sep=';', encoding='utf-8').to_dict('records')
    n = len(fase4)
    fase4n = [r['cpc'] for r in fase4 if r['gold'] == 'No']
    fase4s = [r['cpc'] for r in fase4 if r['gold'] == 'Yes']    
    print(f"{len(fase4n)} ({len(fase4n)/n:.2%}) registros NO ({len(set(fase4n))} personas), {len(fase4s)} ({len(fase4s)/n:.2%}) registros YES ({len(set(fase4s))} personas)")
    # Comprobación de resultados conflictivos (varias entradas enlazadas a la misma persona)
    for (cpc, lis) in group(fase4, lambda r: r['cpc'], lambda r: (r['qid'], r['gold'])):
        if len(lis) > 1:
            ls = {qid for (qid, gold) in lis if gold == 'Yes'}
            if len(ls) > 1:
                print(f"Varias entradas {ls} asignadas al mismo cpc: {cpc}")

