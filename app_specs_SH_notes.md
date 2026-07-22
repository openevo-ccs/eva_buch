# Lehrplananalyse — App Specification

|  |  |
| :---- | :---- |
| **Project** | Companion data app for *Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht* (Hanisch, Springer, 2027\) |
| **Design lead** | Dr. Susan Hanisch |
| **Document status** | Living document — edit specification text in place; use the *Notes for future revisions* block at the end of each section for open questions, ideas, and planned changes rather than inline comments |
| **Last major revision** | 2026-07-20 |

## Table of Contents

1. [Overview](#1-overview)  
2. [Global Data Conventions](#2-global-data-conventions)  
3. [Home](#3-home)  
4. [Lehrplandokumente](#4-lehrplandokumente)  
5. [Schlagwortsuche](#5-schlagwortsuche)  
6. [Themenmodellierung: BERTopic](#6-themenmodellierung-bertopic)  
7. [Themenmodellierung: LDA](#7-themenmodellierung-lda)  
8. [Revision History](#8-revision-history)

---

## 1\. Overview

The Lehrplan Analyse App is a supplementary data interactive built as a GitHub Pages interactive that will live at [http://openevo-ccs.github.io/eva\_buch/app/index.html](http://openevo-ccs.github.io/eva_buch/app/index.html) With a permanent url: [http://lehrplananalyse.openevo.net](http://lehrplananalyse.openevo.net)

The German OpenEvo website for the book: *Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht,* by Dr. Susan Hanisch, is here:  [http://eva-buch.openevo.net](http://eva-buch.openevo.net)

### 1.1 Purpose

It must seamlessly create a comprehensive, intuitive, clean UI/UX for users to engage with data visualizations and access to the raw data from the Lehrplananalyse. All text must be in full, grammatically correct German for this research context.

Whenever possible use the raw GitHub data to generate an amazing, insightful, beautiful data visualization with user-specified options as appropriate, and always enable a raw-data table view (well formatted) with data export options.

### 1.2 Visual Design

**Color and font styles:**

* A mix of whites/light grays/dark grays/dark blacks — depending on light/dark mode selection (default to dark mode) — with core OpenEvo colors as highlights:  
  * \#085E65  
  * \#272D63  
  * With rich gradients within and between these shades and core dark/light elements  
* All menu items and headers should be in Nunito font, with all other text in Roboto font, using smaller font sizes for displaying scientific content as appropriate.

### 1.3 Navigation

**Menu:** (sub-menus may be specified in menu header section descriptions below)

* Home  
* Lehrplandokumente  
* Schlagwortsuche  
* BERTopic  
* LDA

>   
> **Notes for future revisions (Overview):**  
> 

* **The page name shown on the top left of the menu bar should always be: OpenEvo \- Lehrplananalyse in Nunito font, do not show other text there**  
* **The page that one is on should be highlighted by the respective menu item (same color as when hovering over the text)**

---

## 2\. Global Data Conventions

Ensure consistent naming of states (Bundesland) everywhere a state name is displayed or exported. At minimum, in `results.csv` and any other pipeline output where these raw labels still appear, replace the following:

* BaWü → Baden-Württemberg  
* MeckPomm → Mecklenburg-Vorpommern  
* None → KMK

Any other abbreviated or raw state labels found in source data (e.g. "NRW") should likewise be normalized to their full, correctly spelled German name for consistency across all pages of the app.

> **Notes for future revisions (Global Data Conventions):**  
>   
> *The subject name “Ethik, Philo” should be represented in such a way that in csv output, it does not get split into two columns.*  
>   
> *Omit the following search terms from the analysis and output files: Demokratie, Lernen, Konzept, Zukunft*  
---

## 3\. Home

**The following content should be displayed and arranged on the home page:**

**A left panel that takes up about two thirds of the ap width with the following text in a card:**

**Header: Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht \- Eine Lehrplananalyse**

**Paragraph Text:**   
Hier finden Sie ausführliche Informationen zur Lehrplananalyse, die in der Publikation Hanisch (2027). *Evolutionäre Anthropologie als fächerübergreifender Biologieunterricht*. Springer vorgestellt wird. Mehr Informationen zum Projekt finden Sie hier: [http://eva-buch.openevo.net](http://eva-buch.openevo.net)

Untersucht wurden die aktuellen (Stand 2024\) Lehrpläne aller deutschen Bundesländer sowie nationale Dokumente wie einheitliche Prüfungsanforderungen und Bildungsstandards der Fächer Biologie, Ethik/Philosophie, sozialkundlichen Fächer, Geschichte und Psychologie.

Unter dem Menüpunkt *Lehrplandokumente* finden Sie eine tabellarische Übersicht aller Dokumente, die in die Analyse einbezogen wurden, sowie eine Matrix der Anzahl Dokumente pro Fach und Bundesland.

Unter dem Menüpunkt *Schlagwortsuche* finden Sie Informationen und Ergebnisse der Schlagwortsuche.

Unter dem Menüpunkt *BERTopic* finden Sie Informationen und Ergebnisse der Themenmodellierung nach dem BERTopic-Verfahren.

Unter dem Menüpunkt *LDA* finden Sie Informationen und Ergebnisse der Themenmodellierung nach dem LDA-Verfahren.

**On the right side a column with three buttons arranged vertically and spanning the width of the column, containing the following information:**

* **5 Fächer**  
* **295 Lehrplandokumente**  
* **35893 extrahierte Textstellen**

**Below the buttons, a word cloud with all the concepts included in keyword search, with size of concept word by frequency.**

* **Header above the word cloud: Schlagwörter**  
* **Word cloud is circular**  
* **words should be colored using the color and font style information under 1.2**

> **Notes for future revisions (Home):**  
>   
> *Add notes, open questions, or planned changes here.*

---

## 4\. Lehrplandokumente

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
  * Last column: link to the matching .txt file, matched to it via Dateiname, from [LP\_DE\_2026\_1\_txtfiles](https://github.com/openevo-ccs/eva_buch/tree/main/data/LP_DE_2026_1_txtfiles)  
  * Allow user to filter and sort by Bundesland, Fach, Schulart, Jahr, Gesamtwortzahl

>   
> **Notes for future revisions (Lehrplandokumente):**  
>   
> *Show down arrows next to all column labels by default so the user knows that the columns can be sorted.*

---

## 5\. Schlagwortsuche

**Above the interactive interface, a card with a short introduction for non-experts (ca. 100 words) to the keyword search methodology that was used.** 

* include only **one** table on this page  
* Header "Ergebnisse nach Konzept, Fach, Bundesland"  
* User can choose *two dimensions* to be shown in table format, from the following three:  
  * concept   
  * subject  
  * state  
* filter for the third dimension:  
  * if subject × state dimensions chosen: choose concept, or across all concepts total ((this should include all the concepts of the keyword search, not just the concepts that were used for BERTopic and LDA)  
  * if concept × state dimensions chosen: choose subject, or across all subjects  
  * if concept × subject dimensions chosen: choose state, or across all states  
* Toggle between absolute values or relative values (words per 10,000)  
* calculate absolute frequency count from [keyword\_search/out/results.csv](https://github.com/openevo-ccs/eva_buch/blob/main/keyword_search/out/results.csv)  
* calculate relative count (frequency per 10,000 words) from [keyword\_search/out/doc\_word\_counts.csv](https://github.com/openevo-ccs/eva_buch/blob/main/keyword_search/out/doc_word_counts.csv)  
* include a column "Gesamt" at the end: for absolute values, this shows total counts across columns; for relative values, this shows the relative frequency in the total word count of respective documents  
* include a row "Gesamt" at the end with total counts across rows: for absolute values, this shows total counts across rows; for relative values, this shows the relative frequency in the total word count of respective documents  
* Cells shaded by value, excluding "Gesamt" row and column  
  * user can toggle between shading across the whole table, by column, or by row  
* include entropy measure in last column?  
* **Allow user to sort by columns \- display arrow icon next to each column by default so the user knows that the columns can be sorted.**

>   
> **Notes for future revisions (Schlagwortsuche):**  
>   
> *Add notes, open questions, or planned changes here. (Open item carried over from the previous revision: whether/how to add an entropy measure column still needs a methodology decision.)*

---

## 6\. Themenmodellierung: BERTopic

### 6.1 App Design

**Above the interactive interface, a card with a short introduction for non-experts (ca. 150 words) to the BERTopic methodology that was used.**

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
* **Option to de-select all concepts**  
* Toggle local or global projection  
* Toggle 2D or 3D visualization  
* select point size (Punktgröße), with minimum of 2 and maximum of 10, default value 4  
* start/stop orbit  
  * Orbit should start at whatever layout/camera position the cloud is currently in  
* Topics  
  * show/don't show outlier topic  
* **Option to recenter all graphs**  
* 

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
  * **dots have no outline**  
* **Both in 2D and 3D representation,** user can zoom in and out of individual graphs and turn the graphs by mouse.  
* **Both in 2D and 3D representation, when hovering over a point, it shows a rectangular box with information for subject, Bundesland and topic as well as the full text of the excerpt in about 8 lines (adapt box width accordingly).**  
* **Option to download each cloud as image file (png, jpg, tif), in the header bar**

Legend for subjects and topics on the right side.

* one can select subjects/topics from the legend; the selected one is highlighted by making its dots **three** points larger than the rest and by shading them in bright yellow

> **Notes for future revisions (BERTopic):**  
>   
> *The topics in this visualization should be derived from the BERTopic modelling results, i. e. there should be no more than ten topics plus one outlier topic.*  
>   
> **Notes about the BERTopic data analysis:**  
> Why are there only three topics for the concept “Verhalten”? Make sure it is 10 topics.
>
> **2026-07-22 deviation, approved by Dustin — needs Susan's sign-off:** the "only three topics for Verhalten" bug is now root-caused: the original English-trained embedding model was producing undifferentiated clusters (fixed by switching to a genuinely multilingual model, METHODOLOGY.md §3). A full topic-count sweep (METHODOLOGY.md §4.4) then found Verhalten's true natural topic count is 22, not 10 — and the same undercounting affected nearly every concept above ~1,000 documents (Mensch's natural count is 90, for example). Rather than force everything down to 10, the production ceiling was raised to "up to 30 real topics + 1 outlier"; Verhalten and Evolution now run fully uncapped at their natural 22. This exceeds the "no more than ten" line above — flagging explicitly rather than silently overriding it. If Susan prefers the literal 10-topic cap after seeing the richer results, this is a one-line config change to revert (`DEFAULT_NR_TOPICS_CEILING` in `bertopic_pipeline_v2.py`).

---

## 7\. Themenmodellierung: LDA

### 7.1 Analysis Notes

* Within LDA output, use the topic term frequencies data of each concept (CSV by topic, e.g. [here](https://github.com/openevo-ccs/eva_buch/tree/main/lda_topic_modelling/out/Wert/10/topic_term_frequencies)), and collate also across all topics to see frequency of terms across all topics in one list  
* calculate concept co-occurrence or a similar value (how often a searched concept appears in the topic terms of another concept)

### 7.2 Design Notes

**Above the interactive interface, a card with a short introduction for non-experts (ca. 150 words) to the LDA topic modelling methodology that was used.**

Main menu items/app windows arranged in tabs similar to browser tabs (not like menu items):

* Topics and term frequency visualization ("Themen-Visualisierung")  
* Term frequencies table ("Wortfrequenzen")  
* Word clouds of topic terms ("Wortwolken")  
* Topic distribution by subject ("Themen nach Fächern")  
* Concept co-occurrence ("Konzept-Kookkurrenz")

**No selection of concept and topic number at this level, only within each of the windows as specified below**

#### 7.2.1 Topics and term frequency visualization

* Selection of concept (22-concept dropdown list)  
* Selection of model (5, 7, 10\)

Visualization based on a modified pyLDAvis:

* On the left side of the window, an Intertopic Distance Map (via multidimensional scaling)  
  * color each topic differently using the design specifications under 1.2  
  * User can select topics in this map; this selection shows the topic-level frequency in the Top-30 Most Salient Terms bar chart; selected topic should be highlighted by a bright yellow outline of the topic  
* On the right side of the window, a vertical bar chart with Top-30 Most Salient Terms  
  * **can be sorted from top to bottom alphabetically or by overall and (when individual topic selected) topic-level frequency**

#### 7.2.2 Table of term frequencies

* Selection of concept (22-concept dropdown list)  
* Selection of model (5, 7, 10\)  
* The table should be formatted similar to the CSV visualization in GitHub, with shaded color headers and similar font size and row height  
* user can filter and sort by column header \- **the column headers should show an arrow icon by default so the user knows that they can be sorted**  
* Download CSV button

|  | Total across topics | Topic 1 | Topic 2 | Topic 3 | … |
| :---- | :---- | :---- | :---- | :---- | :---- |
| term1 |  |  |  |  |  |
| term2 |  |  |  |  |  |
| … |  |  |  |  |  |

#### 7.2.3 Word clouds of topic terms

* Switch between two modes: "collection of concepts" or "single concept"  
* **Depending on mode, one can select concepts by checkboxes:**  
  * **in collection mode, one can select/deselect up to nine concepts**  
  * **in single-concept mode, one can select just one concept at a time**  
* Word cloud style guide:  
  * Font Nunito  
  * Font size from minimum of **4** to maximum of **40**  
  * Each unique term should have its own color, consistent across the full app and all word clouds \- **use the full RGB color spectrum to ensure font colors are sufficiently different from each other**  
  * All words arranged horizontally  
  * All word clouds in circle format  
  * Above each word cloud is a header with the concept name in font size 16  
* Choose what kind of word cloud:  
  * in collection of concepts mode:  
    * at the top a global wordcloud, across all selected concepts  
    * below word clouds separately for each concept, with font size of words scaled by their frequency *within* that concept  
    * These should be arranged in a matrix depending on the number of selected concepts:  
      * two concepts: side by side  
      * three or four concepts: 2×2 matrix  
      * five or six concepts: 3×2 matrix  
      * seven, eight or nine concepts: 3×3 matrix  
      * etc.  
  * (in single mode) word clouds for each of the 10 topics of a selected concept, with font size of words scaled by their relative frequency within that topic  
    * at the top a global wordcloud for the concept, across all topics  
    * below word clouds per topic arranged in a **3×4** matrix, starting with the most frequent topic

#### 7.2.4 Topic distribution by subject

* Selection of concept (22-concept dropdown list)  
* Selection of model (5, 7, 10\)  
* Topics in rows, subjects in columns, with column and row "Gesamt" containing total values  
* Filter and sort by count of each subject or total  
* Cells shaded by value, **excluding columns and row "Gesamt"**  
  * in dark mode, make sure the shading of cells adapts such that it is not too dark against the black font color  
* Download CSV button

|  | Total across subjects | Biology | Ethics | … |
| :---- | :---- | :---- | :---- | :---- |
| Topic 1 |  |  |  |  |
| Topic 2 |  |  |  |  |
| … |  |  |  |  |

#### 7.2.5 Concept co-occurrence

* matrix of concepts with co-occurrence values  
* the matrix should be formatted similar to the CSV visualization in GitHub, with similar font size and row height  
* cells shaded by value, excluding columns and row "Gesamt"  
  * in dark mode, make sure the shading of cells adapts such that it is not too dark against the black font color  
* **user can sort by column \- the column headers should show an arrow icon by default so the user knows that they can be sorted** 

|  | Mensch | Kultur | … |
| :---- | :---- | :---- | :---- |
| Mensch |  |  |  |
| Kultur |  |  |  |
| … |  |  |  |

* Network graph for concept co-occurrence

>   
> **Notes for future revisions (LDA):**  
>   
> *Add notes, open questions, or planned changes here.*  
>   
> **Notes specifically about the LDA data analysis:**  
>   
> The LDA results differ from the previous results: the topics and their terms are different, and the distribution of topics across subjects is different

---

## 8\. Revision History

| Date | Change | By |
| :---- | :---- | :---- |
| 2026-07-20 | Full spec revision merged from Susan Hanisch's notes (`app_specs_SH_notes.md`); reformatted into this numbered, sectioned document with per-section revision-notes space | Susan Hanisch / Claude |
| 2026-07-18 | Prior working draft | — |

> *Add new rows above as the specification changes. Keep one row per substantive revision, with a one-line summary of what changed and who requested/made the change.*  