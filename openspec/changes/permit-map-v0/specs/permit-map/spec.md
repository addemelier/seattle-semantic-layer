# Spec Delta: permit-map

## Purpose

What a neighbor or homebuyer sees and can do on the permit map page: find an address, see open permits around it, filter them and read one permit's details.

## ADDED Requirements

### Requirement: Map opens on Seattle and keeps its view in the URL
The page at `/` SHALL show a full-window map. With no view in the URL it SHALL open centered on Seattle (47.6062, −122.3321) at zoom 12. The current view SHALL be kept in the URL fragment so that opening a copied link restores the same center and zoom.

#### Scenario: Shared link
- **WHEN** a user opens a URL copied from another user's address bar
- **THEN** the map opens at the same center and zoom

### Requirement: Pins colored by stage
At zoom 12 or closer, the map SHALL show one pin per open permit in view, colored by stage, with a legend naming each stage ("In review", "Issued") and its color. Pins SHALL refresh after the map stops moving. When the API reports `truncated`, the page SHALL say that only the most recent 2,000 permits are shown.

#### Scenario: Pins appear
- **WHEN** the map is at zoom 14 over an area with fixture permits
- **THEN** a pin is drawn for each open permit in view

### Requirement: Zoom-in gate
Below zoom 12, the page SHALL NOT request permits and SHALL show the message "Zoom in to see permits".

#### Scenario: Zoomed out
- **WHEN** the user zooms out to zoom 10
- **THEN** no pins are shown and the zoom-in message is visible

### Requirement: Permit detail panel
Clicking a pin SHALL open a panel showing: address, description, work type, stage, applied / issued / expires dates, valuation (formatted in US dollars, or "Not stated" when missing), housing units added and removed, contractor (or "Not listed"), and a link to the city's permit page that opens in a new tab. The panel SHALL have a close control. On screens narrower than 640 px the panel SHALL appear as a bottom sheet that leaves the top of the map visible.

#### Scenario: Click a pin
- **WHEN** the user clicks a pin
- **THEN** the panel opens with that permit's address and a link to its city page

#### Scenario: Missing valuation
- **WHEN** the clicked permit has no valuation
- **THEN** the panel shows "Not stated" for valuation

### Requirement: Stage and work-type filters
The page SHALL offer checkboxes for each stage and each work type (labels: "In review", "Issued"; "New building", "Addition / alteration", "Demolition", "ADU"), all checked on load. Changing a checkbox SHALL reload pins showing only permits matching the checked values.

#### Scenario: ADUs only
- **WHEN** the user unchecks every work type except ADU
- **THEN** only ADU permits remain on the map

### Requirement: Address search with a 1,000 ft ring
The page SHALL have an address search box. Submitting an address SHALL move the map to the matched point at zoom 16, place a marker there, and draw a ring of radius 1,000 ft (304.8 m) around it. A new search replaces the previous marker and ring. If the address is not found, or the geocoder is unavailable, the page SHALL show a short message and leave the map where it is.

#### Scenario: Found
- **WHEN** the user searches an address the geocoder matches
- **THEN** the map centers on it with a marker and a 1,000 ft ring

#### Scenario: Not found
- **WHEN** the geocoder returns 404
- **THEN** the page shows "Address not found in Seattle" and the map does not move
