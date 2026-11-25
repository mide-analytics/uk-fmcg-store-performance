// Power Query (M) for table 'Weekly Sales'.
// The embedded data literal is omitted from this published copy. Run `scripts/build_powerbi.py` to rebuild it.
let
    Encoded = "<928,179 characters of compressed simulated data omitted; regenerate with `scripts/build_powerbi.py`>",
    Rows = Json.Document(Binary.Decompress(Binary.FromText(Encoded, BinaryEncoding.Base64), Compression.Deflate)),
    Weekly = Table.FromRows(Rows, {"week", "retailer", "region", "store", "format", "category", "units", "sales_pence", "prior_sales_pence", "target_pence", "profit_pence", "promo_pence"})
in Table.TransformColumnTypes(Weekly, {{"week", type date}, {"retailer", type text}, {"region", type text}, {"store", type text}, {"format", type text}, {"category", type text}, {"units", Int64.Type}, {"sales_pence", Int64.Type}, {"prior_sales_pence", Int64.Type}, {"target_pence", Int64.Type}, {"profit_pence", Int64.Type}, {"promo_pence", Int64.Type}}, "en-GB")
