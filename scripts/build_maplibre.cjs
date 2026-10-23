/* Reproducible browser build: no external CDN or module loader required at runtime. */
const fs=require('node:fs'),path=require('node:path'),esbuild=require('esbuild');
const root=path.resolve(__dirname,'..'),destination=path.join(root,'frontend/vendor/maplibre');
fs.mkdirSync(destination,{recursive:true});
esbuild.buildSync({
 stdin:{contents:"import * as core from 'maplibre-gl'; export * from 'maplibre-gl'; core.setWorkerUrl(new URL('maplibre-gl-worker.mjs', document.currentScript.src).href);",resolveDir:root,sourcefile:'maplibre-browser-entry.js'},
 outfile:path.join(destination,'maplibre-gl.js'),bundle:true,minify:true,format:'iife',globalName:'maplibregl',target:['es2022'],legalComments:'inline'
});
for(const name of ['maplibre-gl.css','maplibre-gl-worker.mjs']){
 const source=fs.readFileSync(path.join(root,'node_modules/maplibre-gl/dist',name),'utf8').replace(/\/\/# sourceMappingURL=[^\r\n]*/g,'');
 fs.writeFileSync(path.join(destination,name),source);
}
fs.copyFileSync(path.join(root,'node_modules/maplibre-gl/LICENSE.txt'),path.join(destination,'LICENSE.txt'));
console.log('Built local MapLibre '+require('maplibre-gl/package.json').version);
