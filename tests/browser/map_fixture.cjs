const style={version:8,sources:{streets:{type:'geojson',attribution:'Test map · © OpenStreetMap contributors',data:{type:'FeatureCollection',features:[{type:'Feature',properties:{},geometry:{type:'LineString',coordinates:[[106.68,10.76],[106.72,10.80]]}}]}}},layers:[{id:'background',type:'background',paint:{'background-color':'#e8eee6'}},{id:'streets',type:'line',source:'streets',paint:{'line-color':'#ffffff','line-width':12}}]};
async function stubMaps(page){
 await page.route('https://**/*',route=>route.abort());
 await page.route('https://tiles.openfreemap.org/styles/*',route=>route.fulfill({json:style}));
}
module.exports={stubMaps,style};
