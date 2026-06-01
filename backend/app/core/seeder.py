import os
import pandas as pd
from sqlalchemy import create_engine, inspect

# Database URLs inside the Docker Compose network
DB_CONFIGS = [
    {
        "name": "Movies Database (PostgreSQL)",
        "url": "postgresql://movie_user:movie_password@postgres_movies:5432/movies_db",
        "data_dir": "/app/data/movies/sql",
    },
    {
        "name": "Automotive Database (PostgreSQL)",
        "url": "postgresql://automotive_user:automotive_password@postgres_automotive:5432/automotive_db",
        "data_dir": "/app/data/automotive/sql",
    },
    {
        "name": "Ecommerce Database (MySQL)",
        "url": "mysql+pymysql://ecommerce_user:ecommerce_password@mysql_ecommerce:3306/ecommerce_db",
        "data_dir": "/app/data/ecommerce/sql",
    }
]

def seed_databases():
    print("Starting database seeding process...")
    for db in DB_CONFIGS:
        db_name = db["name"]
        db_url = db["url"]
        data_dir = db["data_dir"]
        
        # Fallback to local paths if running outside docker container
        if not os.path.exists(data_dir):
            local_data_dir = data_dir.replace("/app/data", "./data")
            if os.path.exists(local_data_dir):
                data_dir = local_data_dir
            else:
                print(f"Data directory {data_dir} not found. Skipping {db_name}.")
                continue
            
        try:
            # Add pool_pre_ping to handle transient db startup delays
            engine = create_engine(db_url, pool_pre_ping=True)
            inspector = inspect(engine)
            
            # Check if database is already populated
            existing_tables = inspector.get_table_names()
            
            csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
            if not csv_files:
                print(f"No CSV files found in {data_dir}. Skipping.")
                continue
                
            needs_seeding = False
            for csv_file in csv_files:
                table_name = csv_file.replace('.csv', '')
                if table_name not in existing_tables:
                    needs_seeding = True
                    break
                    
            if not needs_seeding:
                print(f"{db_name} is already fully seeded. Skipping.")
                continue
                
            print(f"Seeding {db_name}...")
            for csv_file in csv_files:
                table_name = csv_file.replace('.csv', '')
                csv_path = os.path.join(data_dir, csv_file)
                
                print(f"  Loading {csv_file} -> table '{table_name}'...")
                df = pd.read_csv(csv_path)
                
                # Write to database
                df.to_sql(name=table_name, con=engine, if_exists='replace', index=False)
                
            print(f"Finished seeding {db_name} successfully.")
        except Exception as e:
            print(f"ERROR: Failed to seed {db_name}: {e}")
            
if __name__ == "__main__":
    seed_databases()
