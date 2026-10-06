# Test fixtures

**All data in this folder is synthetic.** No row describes a real permit, address, contractor or neighborhood boundary.

- `sdci_building_permits_sample.csv` imitates the Seattle SDCI building-permits dataset (Socrata `76t5-zqzr`). Its **column names are unverified**: they were written from memory, and the first real Socrata pull on the server will confirm or correct them. Values are invented to exercise edge cases: every closed and known-open status, case/whitespace variants, an unknown status (`Pending Something`), a duplicated `permitnum` (`6999002-CN`), ADU/AADU/DADU and "accessory dwelling unit" descriptions, a non-ADU word containing "adu", demolitions and new buildings.
- `neighborhoods_sample.geojson` has three rectangular polygons (Ballard, Capitol Hill, Beacon Hill) with a `neighborhood_name` property. They are rough boxes, not real boundaries.

These fixtures drive every build-time verification, so builds never touch the network.
