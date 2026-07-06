# Documents

- [Report in Word Format](Entity_Linking_Report.docx)
- [Report in PDF Format](Entity_Linking_Report.pdf)
- [CPC Database](data/cpc_records.zip)

# Labelling Process

`from labellingprocess import *`

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

`from evaluation import *`

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
