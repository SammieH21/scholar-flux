import pandas as pd
import logging

logger = logging.getLogger(__name__)

class DataFormatter:
    def __init__(self, processed_records):
        self.metadata_df = pd.DataFrame(processed_records)

    def _format_citation(self,row):
        # Assuming 'authors' is a string of author names separated by commas
        authors_formatted = row['authors'] if row['authors'] else ''
        
        # Extract publication year from 'pubdate'
        pub_year = row['pubdate'][:4] if row['pubdate'] else ''
        
        publicationName = row['publicationName'] if row['publicationName'] else ''
        
        # Construct the citation string
        citation = f"{authors_formatted} ({pub_year}). {row['title']}. {publicationName}"
        
        if not pd.isna(row['volume']) and not pd.isna(row['issueNumber']):
            citation += f", {row['volume']}({row['issueNumber']})"
        
        if not pd.isna(row['startingPage']) and not pd.isna(row['endingPage']):
            citation += f", {row['startingPage']}-{row['endingPage']}"
        
        if not pd.isna(row['doi']):
            citation += f". DOI: {row['doi']}"

    def format_all_citations(self):
        # Use the apply method to apply _format_citation to each row
        self.metadata_df['formatted_citation'] = self.metadata_df.apply(self._format_citation, axis=1)


    def filter_metadata(self,record_field,kw,use_regex=False):
        match_msk=self.metadata_df[record_field].str.contains(kw,regex=use_regex)
        self.metadata_df=self.metadata_df.loc[match_msk,:]        
        return self


    def save_metadata(self, path):
        print(f'writing to path: {path}')
        self.metadata_df.to_csv(path, index=False)
        print('Done!')