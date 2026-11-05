SELECT * FROM read_parquet('{{ env_var("FLEET_EXPORTS") }}/fact_toll/*.parquet')
