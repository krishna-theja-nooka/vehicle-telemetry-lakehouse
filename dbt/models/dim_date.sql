SELECT * FROM read_parquet('{{ env_var("FLEET_EXPORTS") }}/dim_date/*.parquet')
