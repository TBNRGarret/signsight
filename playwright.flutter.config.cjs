const base=require('./playwright.config.cjs');
module.exports={...base,testDir:'./tests/flutter_browser',timeout:60000};
