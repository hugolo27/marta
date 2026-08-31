// Pegar en code.earthengine.google.com y correr. Muestra AOI + huella Chaco + held-out sobre
// la capa satelital del Code Editor (capas base, arriba a la derecha). No depende de la service
// account ni de permisos de thumbnails.

var aoi = ee.Geometry.Polygon([[
  [-58.45, -22.5],
  [-58.366667, -22.5],
  [-58.366667, -22.283333],
  [-58.45, -22.283333],
  [-58.45, -22.5]
]]);

var chacoDepartments = ee.FeatureCollection('FAO/GAUL/2015/level1')
  .filter(ee.Filter.and(
    ee.Filter.eq('ADM0_NAME', 'Paraguay'),
    ee.Filter.inList('ADM1_NAME', ['Alto Paraguay', 'Boqueron', 'Presidente Hayes'])
  ));

var heldout = ee.Geometry.Rectangle([-60.23, -22.53, -59.83, -22.17]);  // Filadelfia, Boqueron, aprox.

Map.centerObject(chacoDepartments, 7);
Map.addLayer(chacoDepartments.style({color: '0f766e', fillColor: '00000000', width: 2}), {}, 'Huella Chaco (departamentos)');
Map.addLayer(aoi, {color: 'c2410c'}, 'AOI - Corazon Verde del Chaco');
Map.addLayer(heldout, {color: '1e3a8a'}, 'Held-out - Filadelfia (generalizacion)');

// Sentinel-2 real sobre el AOI, para chequear a ojo si el poligono calza con el bosque/desmonte
var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(aoi)
  .filterDate('2023-01-01', '2023-12-31')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
  .median();

Map.addLayer(s2.clip(aoi.buffer(5000)), {bands: ['B4', 'B3', 'B2'], min: 0, max: 3000}, 'Sentinel-2 RGB sobre el AOI');

// MapBiomas Chaco remapeado a 3 clases (bosque/pasto/cultivo), leyenda real Coleccion 5
// (chaco.mapbiomas.org/en/legend-codes/, no es la leyenda de Brasil/Amazonia).
var BOSQUE = [3, 4, 6, 45];
var PASTO = [15];
var CULTIVO = [18, 19, 57, 58, 36, 9];
var OTHER = [10, 11, 12, 22, 23, 24, 25, 26, 27, 42, 43, 44, 61];
var fromCodes = BOSQUE.concat(PASTO).concat(CULTIVO).concat(OTHER);
var toCodes = BOSQUE.map(function(){return 1;})
  .concat(PASTO.map(function(){return 2;}))
  .concat(CULTIVO.map(function(){return 3;}))
  .concat(OTHER.map(function(){return 0;}));

var mapbiomas = ee.Image('projects/mapbiomas-public/assets/chaco/lulc/collection5/mapbiomas_chaco_collection5_integration_v2');
var labels2019 = mapbiomas.select('classification_2019').remap(fromCodes, toCodes, 0).clip(aoi);
Map.addLayer(labels2019, {min: 0, max: 3, palette: ['9ca3af', '1f8d49', 'edde8e', 'e974ed']}, 'MapBiomas remapeado 2019 (gris=other, verde=bosque, tostado=pasto, magenta=cultivo)');
