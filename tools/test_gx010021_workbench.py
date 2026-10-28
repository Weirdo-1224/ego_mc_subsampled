"""Local file:// UI smoke test with the already installed Edge browser."""
import json
from playwright.sync_api import sync_playwright
from prepare_gx010021_media import OUT,write_json

def main():
    errors=[]; checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((OUT/'index.html').as_uri(),wait_until='load')
        page.wait_for_function("document.getElementById('original').readyState>=1")
        assert page.locator('#tasks button').count()==9
        checks.append('file:// loads embedded data and all 9 tasks without fetch/server')
        duration=page.locator('#original').evaluate('(v)=>v.duration')
        assert abs(duration-696.929567)<0.1
        page.locator('#track').select_option('T3')
        assert page.locator('#tasks button').count()==4
        page.locator('#tasks button').filter(has_text='最初实际打入').click()
        assert '候选打入2枚' in page.locator('#taskDetail').inner_text()
        page.locator('#query').click()
        page.wait_for_function("Math.abs(document.getElementById('original').currentTime-525)<0.1")
        checks.append('track filter, selected candidate details and original query seek work')
        page.locator('#taskDetail .evidence button').first.click()
        page.wait_for_function("document.getElementById('clip').readyState>=2")
        assert abs(page.locator('#clip').evaluate('(v)=>v.duration')-6)<0.1
        assert page.locator('#original').evaluate('(v)=>v.currentTime')==60
        page.locator('#clip').evaluate('(v)=>v.pause()')
        checks.append('historical clip decodes and original jumps to correct absolute source time')
        page.locator('#reviewer').fill('UI TEST DRAFT')
        page.locator('#note').fill('Only a test of PENDING draft export; no human review.')
        page.locator('#save').click()
        assert '已保存' in page.locator('#draftStatus').inner_text()
        with page.expect_download() as dl:
            page.locator('#export').click()
        download=dl.value
        data=json.loads(Path_read(download.path()))
        assert data['maturity']=='CANDIDATE' and data['review']['status']=='PENDING'
        assert all(d['review']['status']=='PENDING' for d in data['drafts'].values())
        checks.append('local draft and JSON export remain CANDIDATE/PENDING')
        page.reload(); page.locator('#track').select_option('T3')
        page.locator('#tasks button').filter(has_text='最初实际打入').click()
        assert page.locator('#reviewer').input_value()=='UI TEST DRAFT'
        checks.append('draft persistence survives reload')
        # Remove test notes from the isolated test browser only.
        page.evaluate('localStorage.clear()');page.reload();page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(OUT/'workbench_desktop.png'),full_page=False)
        assert page.locator('#annotations .annotation').count()==55
        assert page.locator('#timeline .row').count()==27
        page.set_viewport_size({'width':390,'height':844});page.evaluate('window.scrollTo(0,0)')
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.screenshot(path=str(OUT/'workbench_mobile.png'),full_page=False)
        checks.append('55 original annotations, 27 timeline entries and mobile layout render')
        browser.close()
    assert not errors,errors
    report={'status':'PASS','browser':'installed Microsoft Edge headless','mode':'file://',
            'checks':checks,'javascript_errors':errors,'formal_benchmark_run':False}
    write_json(OUT/'ui_tests.json',report);print(json.dumps(report,ensure_ascii=False,indent=2))

def Path_read(path):
    from pathlib import Path
    return Path(path).read_text(encoding='utf-8')

if __name__=='__main__':main()
