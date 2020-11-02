let all_papers = [];
let all_pos = [];
const allKeys = {
    authors: [],
    keywords: [],
    titles: []
}
const filters = {
    authors: null,
    keywords: null,
    title: null
};

const summaryBy = 'keywords' // or: "abstract"

let currentTippy = null;
let brush = null;
const sizes = {
    margins: {l: 20, b: 20, r: 20, t: 20}
}

const explain_text_plot = d3.select('#explain_text_plot');
const summary_selection = d3.select('#summary_selection');
const sel_papers = d3.select('#sel_papers');

const persistor = new Persistor('Mini-Conf-Papers');

let trackhighlight = [];
let color;
let opacity;
const plot_size = () => {
    const cont = document.getElementById('container');
    const wh = Math.max(window.innerHeight - 280, 300)
    let ww = Math.max(cont.offsetWidth - 95, 300)
    if (cont.offsetWidth < 768) ww = cont.offsetWidth - 10.0;

    if ((wh / ww > 1.3)) {
        const min = Math.min(wh, ww)
        return [min, min]
    } else {
        return [ww, ww]
    }
}

const xS = d3.scaleLinear().range([0, 600]);
const yS = d3.scaleLinear().range([0, 600]);
const plot = d3.select('.plot');
// const l_bg = plot.append('g');
// const l_main = plot.append('g');
// const l_fg = plot.append('g');

const updateVis = () => {

    const storedPapers = persistor.getAll();

    const is_filtered = filters.authors || filters.keywords || filters.titles;
    const [pW, pH] = plot_size();

    plot.attr('width', pW).attr('height', pH);
    d3.select('#table_info').style('height', pH / 3 + 'px');

    xS.range([sizes.margins.l, pW - sizes.margins.r]);
    yS.range([sizes.margins.t, pH - sizes.margins.b]);

    treeMap(all_papers);
    // triggerListView("all", root.leaves())


}

const render = () => {
    const f_test = [];
    Object.keys(filters)
      .forEach(k => {filters[k] ? f_test.push([k, filters[k]]) : null});

    let test = d => {
        let i = 0, pass_test = true;
        while (i < f_test.length && pass_test) {
            if (f_test[i][0] === 'titles') {
                pass_test &= d.content['title'] === f_test[i][1];
            } else {
                pass_test &= d.content[f_test[i][0]].indexOf(
                  f_test[i][1]) > -1
            }
            i++;
        }
        return pass_test;
    }

    if (f_test.length === 0) test = d => false;

    all_papers.forEach(paper => paper.is_selected = test(paper));

    updateVis();

}


const tooltip_template = (d) => `
    <div>
        <div class="tt-title">${d.parent.data.name}: ${d.data.name}</div>
     </div>   
`

const start = (track) => {
    const loadfiles = [
        d3.json("papers.json"),
        d3.json('serve_papers_projection.json')
    ]
    if (track != "All tracks") {  
        loadfiles.push(d3.json("track_" + track + ".json"));
    } else {
        trackhighlight =[];
    }
    Promise.all(loadfiles).then(([papers, proj, trackPapers]) => {

        const projMap = new Map()
        proj.forEach(p => projMap.set(p.id, p.pos))

        papers.forEach(p => {
            p.pos = projMap.get(p.id)
        })

        // filter papers without a projection
        all_papers = papers.filter(p => p.pos !== undefined);

        calcAllKeys(all_papers, allKeys);
        setTypeAhead('authors', allKeys, filters, render);


        xS.domain(d3.extent(proj.map(p => p.pos[0])));
        yS.domain(d3.extent(proj.map(p => p.pos[1])));
        
        if (trackPapers) trackhighlight = trackPapers.map(d => d.id);

        updateVis();
    })
      .catch(e => console.error(e))

}

/**
 *  EVENTS
 **/

const updateFilterSelectionBtn = value => {
    d3.selectAll('.filter_option label')
      .classed('active', function () {
          const v = d3.select(this).select('input').property('value')
          return v === value;
      })
}

d3.selectAll('.filter_option input').on('click', function () {
    const me = d3.select(this)

    const filter_mode = me.property('value');
    updateFilterSelectionBtn(filter_mode);

    setTypeAhead(filter_mode, allKeys, filters, render);
    render();
});


function treeMap(data) {
        let trackMappings = {};
        data.forEach(e => {
            if (!(e.content.track in trackMappings)) {
                trackMappings[e.content.track] = {};
            }
            for (let keyword of e.content.keywords) {
                let lowerCasedKeyword = keyword.toLowerCase().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g,"").replace(/\s{2,}/g," ");
                if (lowerCasedKeyword in trackMappings[e.content.track]) {
                    trackMappings[e.content.track][lowerCasedKeyword].push({title: e.content.title, image_path: e.card_image_path, keywords: e.content.keywords, authors: e.content.authors, id: e.id, track: e.content.track});
                } else {
                    trackMappings[e.content.track][lowerCasedKeyword]=[{title: e.content.title, image_path: e.card_image_path, keywords: e.content.keywords, authors: e.content.authors, id: e.id, track: e.content.track}];
                }
            }

        });
        // now filter out all track keys with only 1 value
        let filteredTrackMappings = {};
        Object.entries(trackMappings).forEach(([track, keywords]) => {
            filteredTrackMappings[track] = Object.fromEntries(Object.entries(keywords).filter(([_,v]) => v.length>1));
        });
        function parseTracksToTree(trackMappings) {
            let hierarchalTreeData = {"children": []};
            for (let TRACK_KEY of Object.keys(trackMappings)) {
                let children = [];
                for (let KEYWORD_KEY of Object.keys(trackMappings[TRACK_KEY])) {
                    children.push({"name": KEYWORD_KEY, "group": KEYWORD_KEY, "papers": trackMappings[TRACK_KEY][KEYWORD_KEY], "value": trackMappings[TRACK_KEY][KEYWORD_KEY].length, "colname": "placeholder"});
                }

                hierarchalTreeData["children"].push({"name": TRACK_KEY, "children": children, "colname": "placeholder2"});
            }
            return hierarchalTreeData;
        }
        let treeData = parseTracksToTree(filteredTrackMappings);
        let root = d3.hierarchy(treeData).sum(d => d.value);

        d3.treemap().size([1000,1000]).paddingTop(24).paddingRight(1).paddingInner(2)(root);
        color = d3.scaleOrdinal().domain(Object.keys(trackMappings)).range(d3.schemeSet3);
        opacity = d3.scaleLinear().domain([0, 10]).range([.2, 1]);


        // and to add the text labels
        let is_clicked = false;

        let svg = d3.select("#heatmap");
        svg
        .selectAll("rect")
        .data(root.leaves())
        .enter()
        .append("rect")
            .attr('x', function (d) { return d.x0; })
            .attr('y', function (d) { return d.y0; })
            .attr("class", function(d) { return `recter keyword-${d.data.name.replace(' ','')}` })
            .attr('width', function (d) { return d.x1 - d.x0; })
            .attr('height', function (d) { return d.y1 - d.y0; })
            .style("stroke", "black")
            .style("fill", function(d){ return color(d.parent.data.name)} )
            .style("opacity", function(d){ return opacity(d.data.value)})
            .on("click", function(event, d) {
                // const d = d3.pointer(event);
                console.log(event);
                console.log(d);
                d3.selectAll(`.recter`).style("fill", d => color(d.parent.data.name)).style("opacity", d => opacity(d.data.value)).style("stroke-width", 1)
                d3.selectAll(`.keyword-${d.data.name.replace(' ', '')}`).style("fill", d=> color(d.parent.data.name)).style("opacity", 1).style("stroke-width", 5).style("stroke", "black"); //classed("hover", true);
                triggerListView(d.data.name, root.leaves());
            });
        

            svg
            .selectAll("titles")
            .data(root.descendants().filter(function(d){return d.depth==1}))
            .enter()
            .append("text")
            .attr("x", function(d){ return d.x0})
            .attr("y", function(d){ return d.y0+21})
            .attr("class", "titles")
            .text(function(d){ 
                const pixelsPerCharacter = 5.5
                const numCharacters = Math.floor((d.x1 - d.x0 ) / pixelsPerCharacter);
                if (d.data.name.length > numCharacters) {
                    return `${d.data.name.substring(0,numCharacters)}...`
                }
                return d.data.name;
            })
            .attr("font-size", "11px")
            .attr("fill",  d => color(d.data.name))
        svg
            .append("text")
            .attr("x", 0)
            .attr("y", 20)
            .text("Keywords by Track")
            .attr("font-size", "19px")
            .attr("fill",  "grey" )

        if (!currentTippy) {
            currentTippy = tippy('.recter', {
                content(reference) {
                    let value = d3.select(reference).datum().name;
                    return value;
                },
                onShow(instance) {   
                    const d = d3.select(instance.reference).datum()
                    instance.setContent(tooltip_template(d))
                },
                
                allowHTML: true
            });

        }
        currentTippy.forEach(t => t.enable());
        triggerListView("all", root.leaves());


}

$(window).on('resize', _.debounce(updateVis, 150));

function hexToRgb(hex, alpha) {
    hex   = hex.replace('#', '');
    var r = parseInt(hex.length == 3 ? hex.slice(0, 1).repeat(2) : hex.slice(0, 2), 16);
    var g = parseInt(hex.length == 3 ? hex.slice(1, 2).repeat(2) : hex.slice(2, 4), 16);
    var b = parseInt(hex.length == 3 ? hex.slice(2, 3).repeat(2) : hex.slice(4, 6), 16);
    if ( alpha ) {
       return 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alpha + ')';
    }
    else {
       return 'rgb(' + r + ', ' + g + ', ' + b + ')';
    }
 }

function triggerListView(name, allPapers) {
    let all_sel = [];
    if (name === "all") {
        all_sel = allPapers.map(e => e.data.papers).flat().filter(d => d);
    } else {
        all_sel = allPapers.filter(d => d.data.name == name).map(e => e.data.papers).flat();
    }
    const sel_papers = d3.select('#sel_papers');
    sel_papers.selectAll('.sel_paper').data(all_sel)
    .join('div')
    .attr('class', 'sel_paper')
    .style("background", d => { return hexToRgb(color(d.track), opacity(5));  } )
    .html(
    d => `<div class="p_title">${d.title}</div> <div class="p_authors">${d.authors.join(
        ', ')}</div> <div><b>Keywords</b>: ${d.keywords.join(', ')} </div>`)
    .on('click',
    d => window.open(`paper_${d.id}.html`, '_blank'))
    // .on('mouseenter', d => {
    //     l_main.selectAll('.dot').filter(dd => dd.id === d.id)
    //     .classed('highlight_sel', true)
    //     .each(function () {
    //         if (this._tippy)
    //             this._tippy.show();
    //     })
    // })
    // .on('mouseleave', d => {
    //     l_main.selectAll('.dot').filter(dd => dd.id === d.id)
    //     .classed('highlight_sel', false)
    //     .each(function () {
    //         if (this._tippy)
    //             this._tippy.hide();
    //     })
    // })
}



