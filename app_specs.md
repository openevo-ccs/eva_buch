# Lehrplananalyse App Specifications

The Lehrplan Analyse App is a supplementary data interactive built as a GitHub Pages interactive that will live at [http://openevo-ccs.github.io/eva_buch/app/index.html](http://openevo-ccs.github.io/eva_buch/app/index.html)
With a permanent url: [http://lehrplananalyse.openevo.net](http://lehrplananalyse.openevo.net)

The German OpenEvo website for the book: *Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht,* by Dr. Susan Hanisch, is here:
[https://openevo.eva.mpg.de/projectbase/evo-anthro-buch/?lang=de](https://openevo.eva.mpg.de/projectbase/evo-anthro-buch/?lang=de)

It must seamlessly create a comprehensive, intuitive, clean UI/UX for users to engage with data visualizations and access to the raw data from the Lehrplananalyse. All text must be in full, grammatically correct German for this research context.

Whenever possible use the raw GitHub data to generate an amazing, insightful, beautiful data visualization with user-specified options as appropriate, and always enable a raw-data table view (well formatted) with data export options.

**Color and font styles:**

* A mix of whites/light grays/dark grays/dark blacks — depending on light/dark mode selection (default to dark mode) — with core OpenEvo colors as highlights:
  * #085E65
  * #272D63
  * With rich gradients within and between these shades and core dark/light elements
* All menu items and headers should be in Nunito font, with all other text in Roboto font, using smaller font sizes for displaying scientific content as appropriate.

**Menu:**
(sub-menus may be specified in menu header section descriptions below)

* Home
* Lehrplandokumente
* Schlagwortsuche
* BERTopic
* LDA

# Analysis notes

Ensure consistent naming of states (Bundesland) everywhere a state name is displayed or exported. At minimum, in `results.csv` and any other pipeline output where these raw labels still appear, replace the following:

* BaWü → Baden-Württemberg
* MeckPomm → Mecklenburg-Vorpommern
* None → KMK

Any other abbreviated or raw state labels found in source data (e.g. "NRW") should likewise be normalized to their full, correctly spelled German name for consistency across all pages of the app.

# Home

Hier finden Sie ausführliche Informationen zur Lehrplananalyse, die in der Publikation Hanisch (2027). *Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht*. Springer vorgestellt wird.

Untersucht wurden die aktuellen (Stand 2024) Lehrpläne aller deutschen Bundesländer sowie nationale Dokumente wie einheitliche Prüfungsanforderungen und Bildungsstandards der Fächer Biologie, Ethik/Philosophie, sozialkundlichen Fächer, Geschichte und Psychologie.

Unter dem Menüpunkt *Lehrplandokumente* finden Sie eine tabellarische Übersicht aller Dokumente, die in die Analyse einbezogen wurden, sowie eine Matrix der Anzahl Dokumente pro Fach und Bundesland.

Unter dem Menüpunkt *Schlagwortsuche* finden Sie Informationen und Ergebnisse der Schlagwortsuche.

Unter dem Menüpunkt *BERTopic* finden Sie Informationen und Ergebnisse der Themenmodellierung nach dem BERTopic-Verfahren.

Unter dem Menüpunkt *LDA* finden Sie Informationen und Ergebnisse der Themenmodellierung nach dem LDA-Verfahren.

# Lehrplandokumente

* Text at the top of the page, above tabs: "Hier finden Sie eine Übersicht über alle in der Lehrplananalyse enthaltenen Lehrplandokumente."
* Two tabs within this page: "Matrix" and "Tabelle"
  * tabs should look and feel like browser tabs, not like menu boxes
* **Matrix tab:** Matrix of document count by state and subject
  * calculate from: [Lehrplandokumente Übersicht.csv](https://github.com/openevo-ccs/eva_buch/blob/main/docs/Lehrplandokumente%20%C3%9Cbersicht.csv)
  * states in rows, subjects in columns
    * include column "Gesamt" with total values across states
    * include row "Gesamt" with total values of subjects
  * cells shaded by value (exclude column and row "Gesamt")
  * in dark mode, make sure the shading of cells adapts such that it is not too dark against the black font color
  * allow user to sort by column
* **Tabelle tab:** Table of all documents, filterable and sortable by Fach, Bundesland and Jahr
  * calculate from: [Lehrplandokumente Übersicht.csv](https://github.com/openevo-ccs/eva_buch/blob/main/docs/Lehrplandokumente%20%C3%9Cbersicht.csv)
  * The table should be formatted similar to the CSV visualization in GitHub, with shaded color headers and similar font size and row height
  * Columns from left to right: row ID number from 1–295, Bundesland, Fach, Schulart, Jahr, Gesamtwortzahl, Referenz
  * Last column: link to the matching .txt file, matched to it via Dateiname, from [LP_DE_2026_1_txtfiles](https://github.com/openevo-ccs/eva_buch/tree/main/data/LP_DE_2026_1_txtfiles)
  * Allow user to filter and sort by Bundesland, Fach, Schulart, Jahr, Gesamtwortzahl

# Schlagwortsuche

* include only one table in this page
* Header "Ergebnisse nach Konzept, Fach, Bundesland"
* User can choose *two dimensions* to be shown in table format, from the following three:
  * concept
  * subject
  * state
* filter for the third dimension:
  * if subject × state dimensions chosen: choose concept, or across all concepts total
  * if concept × state dimensions chosen: choose subject, or across all subjects
  * if concept × subject dimensions chosen: choose state, or across all states
* Toggle between absolute values or relative values (words per 10,000)
* calculate absolute frequency count from [keyword_search/out/results.csv](https://github.com/openevo-ccs/eva_buch/blob/main/keyword_search/out/results.csv)
* calculate relative count (frequency per 10,000 words) from [keyword_search/out/doc_word_counts.csv](https://github.com/openevo-ccs/eva_buch/blob/main/keyword_search/out/doc_word_counts.csv)
* include a column "Gesamt" at the end with total counts across columns
* include a row "Gesamt" at the end with total counts across rows
* Cells shaded by value, excluding "Gesamt" row and column
  * user can toggle between shading across the whole table, by column, or by row
* include entropy measure in last column?
* allow user to sort by columns

# Themenmodellierung BERTopic

Kurze Einführung ähnlich wie im Buch

## App design

**Selection options:**

* Concept (select and show up to nine at once)
  * Anpassung
  * Anthropologie
  * Bedürfnis
  * Emotion
  * Evolution
  * Freiheit
  * Gefühl
  * Gen
  * Gerechtigkeit
  * Glück
  * Handeln
  * Konkurrenz
  * Kooperation
  * Kultur
  * Mensch
  * Moral
  * Norm
  * Rationalität
  * Ursache
  * Verhalten
  * Vorurteil
  * Wert
* Toggle local or global projection
* Toggle 2D or 3D visualization
* select point size (Punktgröße), with minimum of 1.5 and maximum of 7, default value 2
* start/stop orbit
  * Orbit should start at whatever layout/camera position the cloud is currently in
* Topics
  * show/don't show outlier topic

**Layout:**

* the boxes for each concept cloud should always be squared (same height and width)
* when choosing one concept, the box takes up the full width
* when two concepts, the two boxes are side by side
* when three or four, it's a 2×2 layout
* when choosing five or six, it's a 3×2 layout
* when choosing between seven and nine, it's a 3×3 layout
* dots colored by:
  * subject area — consistent colors across the whole app:
    * Bio: green
    * Sozialkunde: red
    * Geschichte: orange-yellow
    * Ethik/Philo: purple
    * Psychologie: blue
  * topic
    * distinct colors — but without bright yellow
    * outliers always light gray
* user can zoom in and out of individual graphs and turn the graphs by mouse

Legend for subjects and topics on the right side.

* one can select subjects/topics from the legend; the selected one is highlighted by making its dots two points larger than the rest and by shading them in bright yellow

Can one improve the dimensions of the box that shows up when hovering over a point (like, make it show the full text of the excerpt in about 5 lines, not one line)?

# Themenmodellierung LDA

Kurze Einführung ähnlich wie im Buch

## Analysis notes

* Within LDA output, use the topic term frequencies data of each concept (CSV by topic, e.g. [here](https://github.com/openevo-ccs/eva_buch/tree/main/lda_topic_modelling/out/Wert/10/topic_term_frequencies)), and collate also across all topics to see frequency of terms across all topics in one list
* calculate concept co-occurrence or a similar value (how often a searched concept appears in the topic terms of another concept)

## Design notes

Main menu items/app windows arranged in tabs similar to browser tabs (not like menu items):

* Topics and term frequency visualization ("Themen-Visualisierung")
* Term frequencies table ("Wortfrequenzen")
* Word clouds of topic terms ("Wortwolken")
* Topic distribution by subject ("Themen nach Fächern")
* Concept co-occurrence ("Konzept-Kookkurrenz")

### Topics and term frequency visualization

* Filter by concept (same 22-concept list as above)

Visualization based on a modified pyLDAvis:

* On the left side of the window, a vertical bar chart with Top-30 Most Salient Terms
  * can be sorted from top to bottom alphabetically or by overall and topic-level frequency
* On the right side of the window, an Intertopic Distance Map (via multidimensional scaling)
  * User can select topics in this map; this selection shows the topic-level frequency in the Top-30 Most Salient Terms bar chart

### Table of term frequencies

* Filter by concept (same 22-concept list as above)
* The table should be formatted similar to the CSV visualization in GitHub, with shaded color headers and similar font size and row height
* filter and sort by header
* Download CSV button

|  | Total across topics | Topic 1 | Topic 2 | Topic 3 | … |
| :---- | :---- | :---- | :---- | :---- | :---- |
| term1 |  |  |  |  |  |
| term2 |  |  |  |  |  |
| … |  |  |  |  |  |

### Word clouds of topic terms

* Switch between two modes: "collection of concepts" or "single concept"
* Word cloud style guide:
  * Font Nunito
  * Font size from minimum of 5 to maximum of 30
  * Each unique term should have its own color, consistent across the full app and all word clouds
  * All words arranged horizontally
  * All word clouds in circle format
* Depending on mode, one can select concepts:
  * in collection mode, one can select/deselect several concepts (checkboxes for all concepts)
  * in single-concept mode, one can select just one concept at a time (dropdown field with all concepts)
* Choose what kind of word cloud:
  * Above each word cloud is a header with the concept name in font size 16
  * Global, across all selected concepts
  * Separately for each concept, with font size of words scaled by their frequency within that concept
    * These should be arranged in a matrix depending on the number of selected concepts:
      * two concepts: side by side
      * three or four concepts: 2×2 matrix
      * five or six concepts: 3×2 matrix
      * seven, eight or nine concepts: 3×3 matrix
      * etc.
  * (in single mode) word clouds for each of the 10 topics of a selected concept, with font size of words scaled by their relative frequency within that topic
    * word clouds arranged in a 4×3 matrix, starting with the most frequent topic

### Topic distribution by subject

* Filter by concept (same 22-concept list as above)
* Topics in rows, subjects in columns, with column and row "Gesamt" containing total values
* Filter and sort by count of each subject or total
* Cells shaded by value, excluding columns and row "Gesamt"
  * in dark mode, make sure the shading of cells adapts such that it is not too dark against the black font color
* Download CSV button

|  | Total across subjects | Biology | Ethics | … |
| :---- | :---- | :---- | :---- | :---- |
| Topic 1 |  |  |  |  |
| Topic 2 |  |  |  |  |
| … |  |  |  |  |

### Concept co-occurrence

* matrix of concepts with co-occurrence values
* the matrix should be formatted similar to the CSV visualization in GitHub, with similar font size and row height
* cells shaded by value, excluding columns and row "Gesamt"
  * in dark mode, make sure the shading of cells adapts such that it is not too dark against the black font color

|  | Mensch | Kultur | … |
| :---- | :---- | :---- | :---- |
| Mensch |  |  |  |
| Kultur |  |  |  |
| … |  |  |  |

* Network graph for concept co-occurrence
