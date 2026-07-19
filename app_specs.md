Lehrplananalyse App Specifications

The Lehrplan Analyse App is a supplementary data interactive built as a a GitHub Pages interactive that will live at http://openevo-ccs.github.io/eva_buch/app/index.html
With a permanent url: http://lehrplananalyse.openevo.net 

The German OpenEvo website for the book: Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht, by Dr. Susan Hanisch, is here:
https://openevo.eva.mpg.de/projectbase/evo-anthro-buch/?lang=de 


It must seamlessly create a comprehensive, intuitive, clean UI/UX for users to engage with data visualizations and access to the raw data from the lehrplan analyse. All text must be in full grammatically correct German for this research context. 

When ever possible use the raw github data to generate an amazing insightful beautiful data visualization with user specified options as appropriate, and always enable a raw-data table view (well formatted) with data export options.



Color styles:
A mix of whites/light grays/dark grays/dark blacks - depending on light/dark mode selection (default to dark mode) with core OpenEvo colors as highlights:
#085E65
#272D63
With rich gradients within and between these shades and core dark/light elements



Menu: 
(sub-menus may be specified in menu header section descriptions below)
Home
Lehrplandokumente
Schlagwortsuche
Themenmodellierung BERTopic
Themenodellierung LDA

Home
Hier finden Sie ausführliche Informationen zur Lehrplananalyse, die in der Publikation Hanisch (2027). Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht. Springer vorgestellt wird.

Untersucht wurden die aktuellen (Stand 2024) Lehrpläne aller deutschen Bundesländer sowie nationale Dokumente wie einheitliche Prüfungsanforderungen und Bildungsstandards der Fächer Biologie, Ethik/Philosophie, sozialkundlichen Fächer, Geschichte und Psychologie.

Unter dem Menüpunkt Übersicht Lehrplandokumente finden Sie eine tabellarische Übersicht aller Dokumente, die in die Analyse einbezogen wurden, sowie eine Matrix der Anzahl Dokumente pro Fach und Bundesland.

Unter dem Menüpunkt Schlagwortsuche finden Sie Informationen und Ergebnisse der Schlagwortsuche.

Unter dem Menüpunkt Themenmodllierung LDA finden Sie Informationen und Ergebnisse der Themenmodellierung nach dem LDA-Verfahren.

Unter dem Menüpunkt Themenmodllierung BERTopic finden Sie Informationen und Ergebnisse der Themenmodellierung nach dem BERTopic-Verfahren.

Lehrplandokumente
Csv table - filter and sort by state, subject, year, Gesamtwortzahl
pull from: https://github.com/openevo-ccs/eva_buch/blob/main/docs/Lehrplandokumente%20%C3%9Cbersicht.csv 
link to https://github.com/openevo-ccs/eva_buch/tree/main/data/LP_DE_2026_1_txtfiles and/or add a column with link to .txt file to the table

Csv document count by state and subject - cells shaded by value 
pull from: https://github.com/openevo-ccs/eva_buch/blob/main/keyword_search/out/state_subject_count_matrix.csv
states in rows, subjects in columns
allow user to sort by column

Schlagwortsuche
Csv keywords (keywords.txt), modified by pre-selected list of concepts
https://github.com/openevo-ccs/eva_buch/blob/main/keyword_search/in/keywords.txt 

Csv term results by state and subject (with entropy measure?)
calculate absolute frequency count from https://github.com/openevo-ccs/eva_buch/blob/main/keyword_search/out/results.csv 
calculate relative count (frequency by 10000 words) from https://github.com/openevo-ccs/eva_buch/blob/main/keyword_search/out/doc_word_counts.csv 
User can choose two dimensions to be shown in table format, from the following three
concept
subject 
state 
filter for the third dimension:
if subject by state dimensions chosen): choose concept, or across all concepts total
if concept by stated dimensions chosen): choose subject, or across all subjects
if concept by subject dimensions chosen): choose state, or across all states
Cells shaded by value
across whole table, by column, or by line
Toggle between absolute values or relative values (words per 10.000)
allow user to sort by columns

(if possible: term Excerpt file with filter by concept, subject, state)
may need to preprocess the large file into smaller sections, e.g. by concept
Themenmodellierung BERTopic

Kurze Einführung ähnlich wie im Buch

App design

Selection options:
Dark mode or light mode
Concept (select and show up to six at once→ when choosing one, it takes up the full space, when two they are side by side, when three or four, it’s a 2*2 layout, when choosing five or six, its 3*2 layout) 
Anpassung
Anthropologie
Bedürfnis
Emotion
Evolution
Freiheit
Gefühl
Gen
Gerechtigkeit
Glück
Handeln
Konkurrenz
Kooperation
Kultur
Mensch
Moral
Norm
Rationalität
Ursache
Verhalten
Vorurteil
Wert

colored by:
subject area
consistent colors across 
topic
distinct colors - or shaded scale by frequency
outliers always light gray

Topics 
show/don’t show outlier topic

Toggle local or global projection
select point size (Punktgröße)
Orbit control
speed
elevation
start/stop orbit

subject legend

can one improve the dimensions of the box that shows up when hovering over a point (like, make it show the full text of the excerpt in like 5 lines, not one line)
Themenmodellierung LDA
Kurze Einführung ähnlich wie im Buch
Analysis notes
Within LDA output, use the topic term frequencies data of each concept (csv by topic, e.g. here), and collate also across all topics to see frequency of terms across all topics in one list
calculate concept co-occurrence or similar value? (how often does a searched concept appear in the topic terms of another concept)

Design notes:
Main menu items/app windows: 
Topics and term frequency visualization
Term frequencies table
Topic distribution by subject
Concept co-occurrence
Topics and term frequency visualization
Filter by concept
Anpassung
Anthropologie
Bedürfnis
Emotion
Evolution
Freiheit
Gefühl
Gen
Gerechtigkeit
Glück
Handeln
Konkurrenz
Kooperation
Kultur
Mensch
Moral
Norm
Rationalität
Ursache
Verhalten
Vorurteil
Wert
Similar to vis html in LDA out
Contains Intertopic Distance Map (via multidimensional scaling) and Top-30 Most Salient Terms 
Distance map - can select topics
Terms can be sorted alphabetically or by overall and topic-level frequency

Table of term frequencies 
Filter by concept
Anpassung
Anthropologie
Bedürfnis
Emotion
Evolution
Freiheit
Gefühl
Gen
Gerechtigkeit
Glück
Handeln
Konkurrenz
Kooperation
Kultur
Mensch
Moral
Norm
Rationalität
Ursache
Verhalten
Vorurteil
Wert
filter and sort by header
Download csv button



Total across topics
Topic 1
Topic 2
Topic 3
…
term1










term2










…












Topic distribution by subject
Filter by concept
Anpassung
Anthropologie
Bedürfnis
Emotion
Evolution
Freiheit
Gefühl
Gen
Gerechtigkeit
Glück
Handeln
Konkurrenz
Kooperation
Kultur
Mensch
Moral
Norm
Rationalität
Ursache
Verhalten
Vorurteil
Wert
Topics in rows, subjects in columns, with total column
Filter and sort by count of each subject or total
Download csv button



Total across subjects
Biology
Ethics
…
Topic 1








Topic 2








…










Concept co-occurrence
matrix of concepts with co-occurrence values



Mensch
Kultur
…
Mensch






Kultur






…








