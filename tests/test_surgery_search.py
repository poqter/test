from modules.resources.surgery_search import catalog, normalize, search


def test_catalog_integrity():
    rows = catalog()['rows']
    assert len(rows) == 2686
    assert len({r['name'] for r in rows}) == len(rows)
    assert all(r['name'].strip() for r in rows)
    assert all(r['class3'] in {'1종', '2종', '3종', '비해당'} for r in rows)
    assert all(r['class5'] in {'1종', '2종', '3종', '4종', '5종', '비해당'} for r in rows)


def test_search_normalizes_and_filters_without_inference():
    rows = [
        {'name': '골절 OR/IF 수술', 'class3': '2종', 'class5': '3종'},
        {'name': '다른 수술', 'class3': '1종', 'class5': '비해당'},
    ]
    assert search(rows, 'orif 골절') == rows[:1]
    assert search(rows, '골 절') == rows[:1]
    assert search(rows, class5='비해당') == rows[1:]
    assert search(rows, '골절', class3='1종') == []
    assert search(rows, '존재하지않는수술') == []
    assert normalize('ＯＲ／ＩＦ') == 'orif'


def test_page_search_resets_pagination():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('from modules.resources.surgery_search import run\nrun()').run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 50
    app.button(key='surgery_next').click().run()
    assert app.session_state['surgery_page'] == 2
    app.text_input[0].set_value('백내장').run()
    assert not app.exception
    assert app.session_state['surgery_page'] == 1
    assert all('백내장' in x for x in app.dataframe[0].value['수술명'])
    app.text_input[0].set_value('존재하지않는수술').run()
    assert not app.exception
    assert len(app.dataframe) == 0
    assert len(app.info) == 1

    app.button(key='surgery_reset').click().run()
    assert not app.exception
    assert app.text_input[0].value == ''
    assert len(app.dataframe[0].value) == 50
