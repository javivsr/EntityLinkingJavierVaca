# Documents

(Report in Word Format)[Entity_Linking_Report.docx]

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

