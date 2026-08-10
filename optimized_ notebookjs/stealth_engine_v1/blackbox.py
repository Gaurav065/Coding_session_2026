import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

class BlackboxAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None

    def _load_data(self):
        ext = os.path.splitext(self.file_path)[-1].lower()
        if ext == '.csv':
            self.df = pd.read_csv(self.file_path)
        elif ext in ['.xlsx', '.xls']:
            self.df = pd.read_excel(self.file_path)
        else:
            raise ValueError("Unsupported format! Use CSV or Excel.")

    def clean_and_analyze(self):
        self._load_data()
        # Hidden Cleaning Logic: Drop empty cols, handle nulls
        self.df = self.df.dropna(how='all', axis=1).infer_objects()
        
        stats = {
            "rows": self.df.shape[0],
            "cols": self.df.shape[1],
            "column_names": list(self.df.columns),
            "null_counts": self.df.isnull().sum().to_dict()
        }
        return stats

    def show_relationships(self):
        # Automatically finds numeric columns for a correlation matrix
        numeric_df = self.df.select_dtypes(include=['number'])
        if numeric_df.empty:
            print("No numeric columns found for relationship mapping.")
            return

        fig = px.imshow(numeric_df.corr(), 
                        text_auto=True, 
                        title="Blackbox: Feature Relationship Map")
        fig.show()