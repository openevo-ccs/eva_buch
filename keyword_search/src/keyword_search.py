# Install necessary packages

# Import standard libraries
import zipfile
import os
import pandas as pd
import re
import unicodedata
import sys
from pathlib import Path
import pymupdf 

# Print confirmation message
print("All libraries successfully installed and imported!")

sys.path.append(str(Path(__file__).parent.parent.parent)) 
from config import KW_IN, KW_OUT, DATA_DIR

KEYWORD_PATH = KW_IN / "keywords.txt" #path to keywords
OUT_DIR = KW_OUT
OUT_PATH = KW_OUT / "results.csv"
ZIP_PATH = DATA_DIR / "LP_DE2026_1.zip"
EXTRACT_TO = DATA_DIR / "LP_DE_2026_1/"
context_size = 30


def extract_zip(zip_path, extract_to=None):
    """
    Extract contents of a zip file to a specified directory.
    
    Args:
        zip_path (str): Path to the zip file
        extract_to (str, optional): Directory to extract to. If None, extracts to the same directory as the zip file.
    """
    # Get the directory to extract to
    if extract_to is None:
        extract_to = os.path.dirname(zip_path)
    
    # Make sure the extraction directory exists
    if not os.path.exists(extract_to):
        os.makedirs(extract_to)
    
    # Extract the contents
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    
    print(f"Extracted {zip_path} to {extract_to}")
    return extract_to



def extract_grade(text):
    grade_levels = ['Sekundarstufe',"Sek1","Sek2",'Sek1,2''SekII','Sek 1','Sek 2','Studienstufe']
    
    matched = [word for word in grade_levels if word in text]
    if matched:
        return matched[0]
    pattern = r'\b(?!(?:\d{4}\b))(\d{1,3}(?:[-,]\d{1,3})*)\b'
    
    matches = re.findall(pattern, text)
    if matches:
       return matches[0]
        
    return None

def extract_school_type(text):
    school_types = ["Gym", "Gymnasium", "GemS", "Regionale Schule"]
    matched = [word for word in school_types if word in text]
    if matched:
        return matched[0]
    else:
        matched = [word for word in text.split() if "schule" in word]
        if matched:
            return matched[0]
    return None


def extract_year(text):
    # This pattern matches 4-digit numbers that could represent years
    pattern = r'\b(19\d{2}|20\d{2})\b'
    years = re.findall(pattern, text)
    if years:
        return years[0]
    return None


def get_meta(filename):
    """
    Extract all metadata from filename
    """
    if filename.startswith("."):
        return False
    if filename.split()[0] == "KMK":
        state = "None"
    else:
        state = filename.split()[1]
        if state == "BerlinBB":
            state = "Berlin"
        elif state == "RheinPfalz":
            state = "Rheinland-Pfalz"
    return {
        "file": filename,
        "state": state,
        "school type": extract_school_type(filename),
        "grade": extract_grade(filename),
        "year": extract_year(filename),
    }


def clean_hyphenated_text(text):
    """
    Removes hyphens, line breaks, special characters and extra spaces for nicer excerpts
    """
    # Replace hyphen followed by line break with empty string (removes hyphenation)
    text = re.sub(r'-\s*\n\s*', '', text)
    
    # Remove numbers with periods
    text = re.sub(r'\b\d+(\.\d+)*\.?(?=\s|$)', '', text)

    pattern_dots = r'\.(\s*\.){3,}'
    text = re.sub(pattern_dots, '', text)

    # Remove special characters
    pattern = r'[^a-zA-ZäöüÄÖÜßéèêëçñ\s,.;:/-]'
    text = re.sub(pattern, '', text)
    
    # Replace remaining line breaks with spaces
    text = re.sub(r'\s*\n\s*', ' ', text)
    
    # Optional: normalize extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text



def detect_pdf_orientation(page):
    
    rect = page.rect
    
    width = rect.width
    height = rect.height
    
    if width > height:
        orientation = "landscape"
    elif height > width:
        orientation = "portrait"
    else:
        orientation = "square"
        
    return orientation

def get_word_context(text, start_index, context_size=10):
    """
    Get context of a matched word
    Args:
        context_size (int): Number of words before and after the matched word
    """
    
    words = text.split()
    
   
    char_count = 0
    word_index = -1
    
    for i, word in enumerate(words):
        # Add 1 for the space after each word (except the last one)
        word_len = len(word) + (1 if i < len(words) - 1 else 0) 
        
        if char_count <= start_index < char_count + word_len:
            word_index = i
            break 
        char_count += word_len
    
    if word_index == -1:
        return None
    
     # Calculate the start and end indices for our context window
    start_word = max(0, word_index - context_size)
    end_word = min(len(words), word_index + context_size + 1)
    result = " ".join(words[start_word:end_word]).strip()
    return result

def search_text_for_term(text, lemma, term, context_size=10):
    """
    Search raw text for single search term and exclude terms
    Args:
        context_size (int): Number of words before and after the matched word
    """
    text = clean_hyphenated_text(text)
    results = []
    
   
    pattern = r'\b' + re.escape(term) + r'\b'
    
    if term == "Gen":
        matches = re.finditer(pattern, text)
    else:
        matches = re.finditer(pattern, text, re.IGNORECASE)
    
    for match in matches:
        excerpt = get_word_context(text, match.start(), context_size)
        
        if excerpt:

            excerpt_length = len(excerpt.split(" "))
        
            results.append({
                "search_term": lemma,
                "match_term": term,
                "text_excerpt": excerpt,
                "excerpt_length": excerpt_length,
                
                })
        else:
            print(f"Excerpt could not be created: {excerpt}")

    return results


def normalize_text(text):
    # Replace various dash/hyphen characters with standard hyphen
    dash_chars = [
        '\u002d',  #hyphen-minus
        '\u2010',  # hyphen
        '\u2011',  # non-breaking hyphen
        '\u2012',  # figure dash
        '\u2013',  # en dash
        '\u2014',  # em dash
        '\u2015',  # horizontal bar
        '\u2212',  # minus sign
        '\u00AD',  # soft hyphen
    ]
    
    for char in dash_chars:
        text = text.replace(char, '-')
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    return text

def search_pdf_for_terms(pdf_path, term_dict, context_size=10, header_height=72, footer_height=72):
    """
    Search pdf for a list of search terms
    Args:
        pdf_path (str): File path to pdf
        term_list (list): List of search terms
        exclude_terms (list): Terms to exclude
        context_size (int): Number of words before and after the matched word
    """
    
    doc = pymupdf.open(pdf_path)
    meta = get_meta(os.path.basename(pdf_path))

    results = []
    document = ""
    
    for page_num in range(len(doc)):
    #for page_num in range(26,27):
        
        page = doc[page_num]

        
        # Get page dimensions
        rect = page.rect
        
        width = rect.width
        height = rect.height
        is_landscape = width > height
        
        if is_landscape:
            #print("is landscape")
             
            
            content_rect = pymupdf.Rect(
                rect.x0 + header_height,
                rect.y0 ,
                rect.x1 - footer_height,
                rect.y1 ,
            )
        else:
            
            content_rect = pymupdf.Rect(
                rect.x0,
                rect.y0 + header_height,
                rect.x1,
                rect.y1 - footer_height
            )
        

        
        text = page.get_text(clip=content_rect)
        text = normalize_text(text)
        document += text
    #print(document)
        
        
    for lemma, terms in list(term_dict.items()):
        
        for term in terms:
            if term:
                matches = search_text_for_term(document, lemma, term, context_size)
                
                #print(matches)
                for match_ in matches:
                    #print(match_)
                    
                    #match_["page_number"] = page_num + 1
                    match_.update(meta)
                    results.append(match_)
                #print(results)
    #print(document)        
    return results
   

def search_pdfs_for_terms(folder_path, term_list, context_size=10, header_height =72, footer_height=72):
    """
    Search multiple pdfs for a list of search terms
    Args:
        folder_path (str): Path to directory containing pdfs
        term_list (list): List of search terms
        exclude_terms (list): Terms to exclude
        out_filename (str): Name of result file
        context_size (int): Number of words before and after the matched word
    """
    all_results = []
    print(f"{len(term_list)} search concept(s)")
    
    for root, dirs, files in os.walk(folder_path):
        print(f"Searching in {os.path.basename(root)}...")
        if os.path.basename(root) != "test":
            for i, filename in enumerate(files, 1):
                
                if filename.endswith(".pdf"):
                    #print(f"Searching {filename}... ({i}/{len(files)})")
                    #parent_dir = os.path.basename(root)
                    pdf_path = os.path.join(root,filename)
                    results = search_pdf_for_terms(pdf_path, term_list, context_size, header_height, footer_height) 
                    for result in results:
                        result["subject"] = os.path.basename(root)
                    all_results.extend(results)
                    #print(len(all_results))

    result_df = pd.DataFrame(all_results)         
    #result_df = pd.DataFrame(all_results).sort_values(by=['search_term'], ignore_index=True)
    return result_df


def execute_search(basepath: Path, 
                   keyword_path: Path, 
                   out_path: Path, 
                   context_size: int = 10,
                   search_term: str | None = None,
                   header_height: int = 72,
                   footer_height: int = 72):
    """
    Reads in list of search terms and performs search
    Args:
        folder_path (str): Path to directory containing pdfs
        term_list (list): List of search terms
        exclude_terms (list): Terms to exclude
        out_filename (str): Name of result file
        context_size (int): Number of words before and after the matched word
    """
    
    with open(keyword_path, 'r') as file:
        lines = file.readlines()
        
    if "\n" in lines:
        lines.remove("\n")
    concept_dict = {line.split(",")[0].strip(): [item.strip() for item in line.split(",")] for line in lines}
    
    if search_term == None:
        print("No search term selected, looking for all terms in the list")
        result_df = search_pdfs_for_terms(basepath, concept_dict, context_size, header_height, footer_height)
    else:
        search_terms = {search_term : concept_dict[search_term]}
        result_df = search_pdfs_for_terms(basepath, search_terms, context_size, header_height, footer_height)
    try:
        result_df.to_csv(out_path, index=None)
        print(f"Saved to {out_path}")
    except:
        print("Could not save results")
    return result_df


# Get words per document
def count_words(folder_path):
    word_counts = []
    for root, dirs, files in os.walk(folder_path):
        #print(dirs)
        for filename in files:
            
            if filename.endswith(".pdf"):
               
                pdf_path = os.path.join(root,filename)
                doc = pymupdf.open(pdf_path)
    

                word_count = 0
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    text = page.get_text("text")
                    
                    if text:
                        words = text.split()
                        word_count += len(words)
                       
                df_row = get_meta(filename)
                df_row["subject"] = os.path.basename(root)
                df_row["word_count"] = word_count
                word_counts.append(df_row)
    df_counts = pd.DataFrame(word_counts)
    df_counts.to_csv(f"{OUT_DIR}/doc_word_counts.csv", index=None)        
    return df_counts
    
# Get state/subject counts
def make_pivot(df, column_a, column_b):
    df = df[["file","state","subject"]].drop_duplicates()
    matrix = df.pivot_table(index=column_a, columns=column_b, aggfunc='size', fill_value=0)
    matrix['Total'] = matrix.sum(axis=1)

    # Add column totals
    matrix.loc['Total'] = matrix.sum(axis=0)
    matrix.to_csv(f"{OUT_DIR}/state_subject_count_matrix.csv")
    return matrix

# Get term counts
def count_terms(df, keyword_path):
    count_dict = df['search_term'].value_counts().to_dict()
    
    with open(keyword_path, 'r') as file:
        lines = file.readlines()
    if "\n" in lines:
        lines.remove("\n")
    concept_dict = {line.split(",")[0].strip(): [item.strip() for item in line.split(",")] for line in lines}
    
    for k,v in concept_dict.items():
        if k not in count_dict:
            count_dict[k] = 0
            
    df_counts = pd.DataFrame(list(count_dict.items()), columns=['Search concept', 'Count'])
    df_counts.to_csv(f"{OUT_DIR}/term_count.csv")
    return df_counts


def main():

    DATA_PATH = extract_zip(ZIP_PATH, EXTRACT_TO)

    result_df = execute_search(
        basepath = DATA_PATH,
        keyword_path=KEYWORD_PATH,
        out_path=OUT_PATH,
        context_size=context_size,
        header_height=72,
        footer_height=72,
    )
    pivot_df = make_pivot(result_df, "state", "subject")
    term_count_df = count_terms(result_df, KEYWORD_PATH)
    word_counts = count_words(DATA_PATH)

if __name__ == "__main__":
    main()
