# Documents

- [Report in Word Format](Entity_Linking_Report.docx)
- [Report in PDF Format](Entity_Linking_Report.pdf)
- [CPC Database](data/cpc_records.zip)

# Production

The [master.csv](data/production/master.csv) file contains the results of the linking between CPC records (*cpc* field, which contains the record ID) and Wikidata entities (*qid* field). It has 152,589 rows (one for each CPC record), and the *qid* field can have the following values:
* A hyphen (-) if it has not been processed
* The text NIL if it could not be linked to any entity
* The QID of the entity if it could be linked to that entity

The operations that can be performed are:

## Creation and population of master file

The following function calls create the file and populate it with the labeling and test results (they only need to be done once)

`from src.labellingprocess import *`

`create_master_file(FILE_CPC_ALL, FILE_MASTER)`

`load_data(FILE_MASTER, 'data/labelling')`

`load_data(FILE_MASTER, 'data/labelling')`

## Processing of registers of CPC

This can be done in two ways:
- By providing a list of the ID fields of the CPC records to be processed.
- By requesting that the first n records of the master file that have not yet been processed be processed.

`process_cpcs(['D02945', 'K00623'])`

`process_num(100)`

In both cases, the information in the [master.csv](data/production/master.csv) file is automatically updated.

Detailed information about the linking process can be obtained using the following function:

`info_cpc('Z00225')`

                    CPC             Wikidata      Rank
    Id           Z00225            Q12797219
    Name     Nada Zagar           Nada Žagar         1
    Birth          1924                 1924         1
    Sex               f                    f         1
    Country  Yugoslavia  Regno di Jugoslavia         1
    City        Dobrova      Srednja Dobrava  0.857143
    Occup     casalinga           partigiano        -1

# Labelling Process

`from src.labellingprocess import *`

## Initial Step: Obtain the CPC (Casellario Politico Centrale) database

`download_cpc(FILE_CPC_ALL, PROGRESS_CPC)`

## Analysis of the information contained in CPC

`cpc_analysis(FILE_CPC_ALL)`

## Step 1-a: Creating a subset for labeling

`add_subset(FILE_CPC_ALL, FILE_CPC_EXTRACT, 0.02)`

## Step 1-b: Direct search on WikiData

`step1b(FILE_CPC_EXTRACT, FILE_STEP1)`

## Step 2-a: Complete records with SPARQL-WikiData

`step2a(FILE_CPC_EXTRACT, FILE_STEP1, FILE_STEP2a)`

## Step 2-b: Add extra fields

`step2b(FILE_STEP1, FILE_STEP2a, FILE_STEP2b)`

## Step 3: Add rank fields

`step3(FILE_STEP2b, FILE_STEP3, FILE_LABELLING)`

From this point forward, the [labelling.csv](data/labelling.csv) file is available for the manual labeling process.

# Evaluation of Models

`from src.evaluation import *`

## Loading of data

`df = pd.read_csv(FILE_LABELLING, sep=';', encoding='utf-8')`

`X = df[COLS].to_numpy(dtype=float)`

`y_true = (df["gold"] == "Yes").astype(int).to_numpy()`

## Heuristics model

`show_metrics(y_true, heuristics(X, y_true, UMBRAL))`

## Logistic regression model

`model = regression(X, y_true)`

`show_metrics(y_true, model.predict(X))`

## Random forest model

`model = forest(X, y_true)`

`show_metrics(y_true, model.predict(X))`

## XG-Boost model

`model = xgboost(X, y_true)`

`show_metrics(y_true, model.predict(X))`
    Father    Stanislao                              0
    Affil     comunista                              0
    Alias
    Linked       LINKED
