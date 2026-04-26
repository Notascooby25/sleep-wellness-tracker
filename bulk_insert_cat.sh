#!/bin/bash

# OPTIONAL: Reset all categories + activities (only works if you have this endpoint)
# curl -X DELETE http://localhost:8000/categories/reset

# CREATE CATEGORIES IN ORDER (IDs will be 1–5)
curl -X POST http://localhost:8000/categories/ -H "Content-Type: application/json" -d '{"name":"Lifestyle"}'
curl -X POST http://localhost:8000/categories/ -H "Content-Type: application/json" -d '{"name":"Headache Issues"}'
curl -X POST http://localhost:8000/categories/ -H "Content-Type: application/json" -d '{"name":"Health"}'
curl -X POST http://localhost:8000/categories/ -H "Content-Type: application/json" -d '{"name":"Before Sleep"}'
curl -X POST http://localhost:8000/categories/ -H "Content-Type: application/json" -d '{"name":"During Sleep"}'

echo "Categories created:"
echo "1 = Lifestyle"
echo "2 = Headache Issues"
echo "3 = Health"
echo "4 = Before Sleep"
echo "5 = During Sleep"
