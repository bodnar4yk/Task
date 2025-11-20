import pandas as pd
# example
file_path_1 = 'C:\\Users\\Dinamicka Laptop\\Downloads\\response_1763658521119.csv'
file_path_2 = 'C:\\Users\\Dinamicka Laptop\\Downloads\\response_1763658205164.csv'

df1 = pd.read_csv(file_path_1)

df2 = pd.read_csv(file_path_2)

combined_df = pd.concat([df1, df2], ignore_index=True)

print(type(combined_df))

