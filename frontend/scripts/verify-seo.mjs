import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
const root = path.resolve(import.meta.dirname, '..');
function load(file, dependencies = {}) {
  const module = { exports: {} };
  const js = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  new Function('require', 'module', 'exports', js)(name => { assert.ok(name in dependencies, name); return dependencies[name]; }, module, module.exports);
  return module.exports;
}
const original = { ...process.env };
try {
  for (const [origin, expected] of [['https://mysecop.co', true], ['https://dev.mysecop.co', false], ['https://stg.mysecop.co', false], ['http://localhost:8000', false]]) {
    process.env.NODE_ENV = 'production';
    delete process.env.NEXT_PUBLIC_SITE_URL;
    process.env.NEXT_PUBLIC_API_URL = origin;
    const seo = load('lib/seo.ts');
    assert.equal(seo.indexPublicPages, expected);
    const robots = load('app/robots.ts', { '@/lib/seo': seo }).default();
    const sitemap = load('app/sitemap.ts', { '@/lib/seo': seo }).default();
    const contact = seo.publicMetadata('/contacto', 'Contacto', 'Descripción');
    assert.equal(contact.alternates.canonical, '/contacto');
    assert.equal(contact.title.absolute, 'Contacto | MySECOP');
    assert.equal(contact.robots.index, expected);
    assert.deepEqual(sitemap.map(x => x.url), expected ? [origin + '/', origin + '/contacto'] : []);
    assert.ok(sitemap.every(x => !x.lastModified));
    assert.equal(robots.rules[0].allow, '/');
    assert.ok(!JSON.stringify(robots.rules[0].disallow).includes('/app'));
    assert.equal(Boolean(robots.sitemap), expected);
    const config = (await import('../next.config.mjs')).default;
    const headers = await config.headers();
    assert.equal(headers.some(x => x.source === '/:path*'), !expected);
    if (expected) for (const route of ['/app/:path*', '/api/:path*', '/registro', '/legal/:path*']) assert.ok(headers.some(x => x.source === route));
    console.log(`PASS ${origin}: canonical, robots, sitemap and headers`);
  }
} finally { process.env = original; }
