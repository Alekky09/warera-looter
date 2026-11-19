const fs = require("fs");
const {minify} = require("html-minifier-terser");
async function build() {
    const html = fs.readFileSync("src/index.html", "utf-8");
    const result = await minify(html, {
        collapseWhitespace: true,
        removeComments: true,
        removeRedundantAttributes: true,
        removeEmptyAttributes: true,
        minifyCSS: true,
        minifyJS: {
            mangle: true,
            compress: true,
        }
    });
    fs.mkdirSync("dist", {recursive: true});
    fs.writeFileSync("dist/index.html", result);
    console.log("Index file successfully minified!");
}

build();