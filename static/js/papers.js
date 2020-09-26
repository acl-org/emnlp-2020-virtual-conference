let allPapers = [];
const allKeys = {
    authors: [],
    keywords: [],
    session: [],
    titles: [],
}
const filters = {
    authors: null,
    keywords: null,
    session: null,
    title: null,
};

let render_mode = 'list';
let current_card_index = -1;

const removeOldFocus = () => {
    if (current_card_index !== -1) {
        $('.card').eq(current_card_index).removeClass('card-active')
    }
}

const updateCardIndex = (card_index) => {
    removeOldFocus()

    if (card_index < -1) return;

    current_card_index = card_index;
    if (current_card_index == -1) return;

    let card = $('.card').eq(current_card_index)
    
    card.addClass('card-active');
    // $('.card').eq(current_card_index).focus();

    if (!card.visible()) {
        var $window = $(window),
        $element = card;
        elementTop = $element.offset().top,
        elementHeight = $element.height(),
        viewportHeight = $window.height(),
        scrollIt = elementTop - ((viewportHeight - elementHeight) / 2);

        // $window.scrollTop(scrollIt);
        $("html, body").animate({ scrollTop: scrollIt }, 50);
    }

    let isShown = ($("#quickviewModal").data('bs.modal') || {})._isShown;
    if (isShown) 
        $('.card').eq(current_card_index).find(".btn-quickview")[0].click();
}

const setUpKeyBindings = () => {

    Mousetrap.bind('right', () => {
        if (current_card_index >= $('.card').length - 1) 
            return;
        
        updateCardIndex(current_card_index+1);
    });

    Mousetrap.bind('left', () => {
        if (current_card_index <= 0) 
            return;
        
        updateCardIndex(current_card_index-1);
    });

    Mousetrap.bind('space', () => {
        if (current_card_index == -1)
            return

        let isShown = ($("#quickviewModal").data('bs.modal') || {})._isShown
        if (isShown) 
            $('#quickviewModal').modal('toggle')
        else
            $('.card').eq(current_card_index).find(".btn-quickview")[0].click()
    })

    Mousetrap.bind('esc', () => {
        let isShown = ($("#quickviewModal").data('bs.modal') || {})._isShown
        if (isShown) {
            $('#quickviewModal').modal('hide')
            return;
        }
        
        updateCardIndex(-1);
    })

    // $('.container').click(()=>{
    //     updateCardIndex(-1);
    // })
}

const persistor = new Persistor('Mini-Conf-Papers');

const updateCards = (papers) => {
    const storedPapers = persistor.getAll();
    papers.forEach(
      openreview => {
          openreview.content.read = storedPapers[openreview.id] || false
      })

    papers.map((e, idx, array) => {
        e.index_in_list = idx;
        return e;
    })

    const readCard = (iid, new_value) => {
        persistor.set(iid, new_value);
        // storedPapers[iid] = new_value ? 1 : null;
        // Cookies.set('papers-selected', storedPapers, {expires: 365});
    }

    const all_mounted_cards = d3.select('.cards')
      .selectAll('.myCard', openreview => openreview.id)
      .data(papers, d => d.number)
      .join('div')
      .attr('class', 'myCard col-xs-6 col-md-4')
      .html(card_html)

    all_mounted_cards.select('.card-title')
      .on('click', function (d) {
          const iid = d.id;
          all_mounted_cards.filter(d => d.id === iid)
            .select(".card-title").classed('card-title-visited', function () {
              const new_value = true;//!d3.select(this).classed('not-selected');
              readCard(iid, new_value);
              return new_value;
          })
      })

    all_mounted_cards.select('.btn-quickview')
      .on('click', function (d) {
          const iid = d.id;
          updateCardIndex(d.index_in_list)
          openQuickviewModal(d);
          d3.event.stopPropagation();
      })

    all_mounted_cards.select(".checkbox-paper")
      .on('click', function (d) {
          const iid = d.id;
          const new_value = !d3.select(this).classed('selected');
          readCard(iid, new_value);
          d3.select(this).classed('selected', new_value)
          d3.select(this.closest('.greenbox-paper')).classed('selected', new_value)
      })


    lazyLoader();
}

const openQuickviewModal = (paper) => {
    updateModalData(paper);
    $('#quickviewModal').modal('show')
}

const updateModalData = (paper) => {
    $('#modalTitle').text(paper.content.title);
    $('#modalAuthors').text(paper.content.authors.join(', '));

    $('#modalPaperType').text(paper.content.paper_type);
    $('#modalPaperTrack').text(paper.content.track);

    $('#modalAbstract').text(paper.content.abstract);

    $('#modalChatUrl').attr('href', `https://${chat_server}/channel/${paper.forum}`);
    $('#modalPresUrl').attr('href', `https://slideslive.com/${paper.presentation_id}`);
    $('#modalPaperUrl').attr('href', paper.content.pdf_url);
    $('#modalPaperPage').attr('href', `paper_${paper.id}.html`);

    let keywordsHtml = paper.content.keywords.map(modal_keyword).join('\n');
    $('#modalKeywords').html(keywordsHtml);

    let sessionsHtml = paper.content.sessions.map(s => modal_session_html(s, paper)).join('\n');
    $('#modalSessions').html(sessionsHtml);

    $('#quickviewModal').modal('handleUpdate');
}

const moveArrayItem = (array, fromIndex, toIndex) => {
    const arr = [...array];
    arr.splice(toIndex, 0, ...arr.splice(fromIndex, 1));
    return arr;
}

function sortSelectedFirst(array) {
    const selections = Object.keys(persistor.getAll())
    for (let i = array.length - 1; i > 0 ; i--) {
        if (selections.includes(array[i].id)) {
            array = moveArrayItem(array, i, 0)
        }
    }
    allPapers = array;
}

/* Randomize array in-place using Durstenfeld shuffle algorithm */
function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        const temp = array[i];
        array[i] = array[j];
        array[j] = temp;
    }
}

const render = () => {
    current_card_index = -1;

    const f_test = [];

    updateSession();

    Object.keys(filters)
      .forEach(k => {filters[k] ? f_test.push([k, filters[k]]) : null})

    //  console.log(f_test, filters, "--- f_test, filters");
    if (f_test.length === 0) updateCards(allPapers)
    else {
        const fList = allPapers.filter(
          d => {

              let i = 0, pass_test = true;
              while (i < f_test.length && pass_test) {
                  if (f_test[i][0] === 'titles') {
                      pass_test &= d.content['title'].toLowerCase()
                        .indexOf(f_test[i][1].toLowerCase()) > -1;

                  } else {
                      if (f_test[i][0] === 'session' || f_test[i][0] === 'sessions' ) {
                          pass_test &= d.content['sessions'].some(
                              function (item) {
                                  return item.session_name === f_test[i][1];
                              }
                          );
                      } else {
                          console.log(f_test[i])
                          pass_test &= d.content[f_test[i][0]].indexOf(
                            f_test[i][1]) > -1
                      }
                  }
                  i++;
              }
              return pass_test;
          });
        // console.log(fList, "--- fList");
        updateCards(fList)
    }

}

const updateFilterSelectionBtn = value => {
    d3.selectAll('.filter_option label')
      .classed('active', function () {
          const v = d3.select(this).select('input').property('value')
          return v === value;
      })
}

const updateSession = () => {
    const urlSession = getUrlParameter("session");
    let sessionName;
    if (urlSession) {
        filters['session'] = urlSession;
        // special processing for regular QA session and Demo session
        if (urlSession.startsWith("D")) {
          sessionName = "Demo Session " + urlSession.substring(1)
        } else {
          sessionName = "Session " + urlSession
        }
        d3.select('#session_name').text(sessionName);
        d3.select('.session_notice').classed('d-none', null);
        return true;
    } else {
        filters['session'] = null
        return false;
    }
}

/**
 * START here and load JSON.
 */
const start = (track) => {
    // const urlFilter = getUrlParameter("filter") || 'keywords';
    const urlFilter = getUrlParameter("filter") || 'titles';
    setQueryStringParameter("filter", urlFilter);
    updateFilterSelectionBtn(urlFilter);

    var path_to_papers_json;
    if (track === "All tracks") {
      path_to_papers_json = "papers.json";
    } else {
      path_to_papers_json = "track_"  + track + ".json";
    }

    d3.json(path_to_papers_json).then(papers => {
        shuffleArray(papers);

        allPapers = papers;
        calcAllKeys(allPapers, allKeys);
        setTypeAhead(urlFilter,
          allKeys, filters, render);
        updateCards(allPapers);

        const urlSearch = getUrlParameter("search");
        if ((urlSearch !== '') || updateSession()) {
            filters[urlFilter] = urlSearch;
            $('.typeahead_all').val(urlSearch);
            render();
        }


    }).catch(e => console.error(e))
};


/**
 * EVENTS
 * **/

d3.selectAll('.filter_option input').on('click', function () {
    const me = d3.select(this);

    const filter_mode = me.property('value');
    setQueryStringParameter("filter", filter_mode);
    setQueryStringParameter("search", '');
    updateFilterSelectionBtn(filter_mode);


    setTypeAhead(filter_mode, allKeys, filters, render);
    render();
});

d3.selectAll('.remove_session').on('click', () => {
    setQueryStringParameter("session", '');
    render();

});

d3.selectAll('.render_option input').on('click', function () {
    const me = d3.select(this);
    render_mode = me.property('value');

    render();
});

d3.select('.visited').on('click', () => {
    sortSelectedFirst(allPapers);

    render();
})

d3.select('.reshuffle').on('click', () => {
    shuffleArray(allPapers);

    render();
})



/**
 * CARDS
 */

const keyword = kw => `<a href="papers.html?filter=keywords&search=${kw}"
                       class="text-secondary text-decoration-none">${kw.toLowerCase()}</a>`;

const card_image = (openreview, show) => {
    if (show) return ` <center><img class="lazy-load-img cards_img card-img" data-src="${openreview.card_image_path}" width="80%"/></center>`
    else return ''
};


const card_detail = (openreview, show) => {
    if (show)
        return ` 
        <br/>
        <p class="card-text"> ${openreview.content.tldr}</p>
        <p class="card-text"><span class="font-weight-bold">Keywords:</span>
            ${openreview.content.keywords.map(keyword).join(', ')}
        </p>
`
    else return ''
};

//language=HTML
const card_html = openreview => `
        <div class="card card-dimensions${(render_mode == 'detail')? '-detail' : render_mode !== 'list'? '-image' : ''}">
            <div class="card-body">

                <a href="paper_${openreview.id}.html"
                target="_blank"><h5 class="card-title ${openreview.content.read ? 'card-title-visited' : ''}">${openreview.content.title}</h5>
                </a>
                <h6 class="card-subtitle mb-2 text-muted">${openreview.content.authors.join(', ')}</h6>
                
                ${card_image(openreview, render_mode !== 'list')}

                ${card_detail(openreview, (render_mode === 'detail'))}
            </div>

            <div class="card-footer">
                    <button type="button" class="btn btn-sm btn-outline-primary"><i class="fas fa-plus"></i> Add to Favorite</button>
                    <button type="button" class="btn btn-sm btn-outline-primary btn-quickview"><i class="fas fa-bars"></i> Quickview</button>
            </div>
        </div>

        `


const modal_keyword = kw => `<a class="badge badge-pill badge-info" 
                                href="papers.html?filter=keywords&search=${kw}">${kw.toLowerCase()}</a>`

const getSessionTimeString = (sess) => {
    let start_time = moment.utc(sess.start_time, 'ddd, DD MMM YYYY HH:mm:ss');
    let end_time = moment.utc(sess.end_time, 'ddd, DD MMM YYYY HH:mm:ss');

    let guess_tz = moment.tz.guess(true);
    let local_start = start_time.tz(guess_tz);
    let local_end = end_time.tz(guess_tz);

    if (local_start.dayOfYear() === local_end.dayOfYear()){
        time_str = `${local_start.format('MMM D, HH:mm')}-${local_end.format('HH:mm')}`;
    } else {
        time_str = `${local_start.format('MMM D HH:mm')}-${local_end.format('MMM D HH:mm')}`;
    }

    return time_str;
}

const getCalendarLinks = (sess, paper) => {
    
    let start_time = moment.utc(sess.start_time, 'ddd, DD MMM YYYY HH:mm:ss');
    let end_time = moment.utc(sess.end_time, 'ddd, DD MMM YYYY HH:mm:ss');

    return addToCalendarData({
        options: {
          class: 'my-class',
          id: 'my-id'
        },
        data: {
          title: paper.content.title.replace("#", " "),
          start: new Date(start_time.format('YYYY-MM-DDTHH:mm:ss')),
          end: new Date(end_time.format('YYYY-MM-DDTHH:mm:ss')),
          timezone: 'UTC',
          address: sess.zoom_link,
          description: `${site_url}/paper_${paper.id}.html`,
        }
    });
}

const modal_session_html = (session, paper) => {
    let calendar_links = getCalendarLinks(session, paper);
    for (const key of Object.keys(calendar_links)) 
        calendar_links[key] = $($.parseHTML(calendar_links[key]))
            .addClass('dropdown-item')
            .prop('outerHTML');
    
    return `<div class="media paper-modal-session">
            <div class="align-self-center mr-2 bg-primary paper-modal-session-name text-light"> 
              ${session.session_name}
            </div>
            <div>
              <div>${getSessionTimeString(session)}</div>
              <div class="btn-group paper-modal-session-calendar-btn">
                <button class="btn btn-link btn-sm dropdown-toggle" type="button" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                  Add to Calendar
                </button>
                <div class="dropdown-menu">  
                    ${calendar_links['google']}
                    ${calendar_links['off365']}
                    ${calendar_links['outlook']}
                    ${calendar_links['ical']}
                </div>
              </div>
            </div>
        </div>`;
}
//<div class="pp-card pp-mode-` + render_mode + ` ">
//            <div class="pp-card-header greenbox-paper ${openreview.content.read ? 'selected' : ''}">
//            <div class="" style="position: relative; height:100%">
//                <div style="display: block;position: absolute; bottom:35px;left: 0px;">
//                    <div class="checkbox-paper ${openreview.content.read ? 'selected' : ''}">✓</div>
//                </div>
//                <a href="paper_${openreview.id}.html"
//                target="_blank"
//                   class="text-muted">
//                   <h5 class="card-title" align="center"> ${openreview.content.title} </h5></a>
//                <h6 class="card-subtitle text-muted" align="center">
//                        ${openreview.content.authors.join(', ')}
//                </h6>
            //    ${card_image(openreview, render_mode !== 'list')}
//            </div>
//            </div>
//
//                ${card_detail(openreview, (render_mode === 'detail'))}
//        </div>