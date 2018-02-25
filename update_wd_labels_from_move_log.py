# Task description:
# https://www.wikidata.org/wiki/Wikidata:Requests_for_permissions/Bot/DanmicholoBot_8

import re
import os
import logging
import pywikibot
from prompter import prompt, yesno
from pywikibot import pagegenerators
from pywikibot.exceptions import NoPage

# ------------------------------------------------------------
# Config:

configs = {
    'nb': {
        'siteid': 'no',
        'lang': 'nb',
        'dont_introduce': [' ('],
    },
    'nn': {
        'siteid': 'nn',
        'lang': 'nn',
        'dont_introduce': [' (', ' i '],
    },
    'sv': {
        'siteid': 'sv',
        'lang': 'sv',
        'dont_introduce': [' (', ', ', '#'],
    },
    'da': {
        'siteid': 'da',
        'lang': 'da',
        'dont_introduce': [' (', ' i '],
    },
    'en': {
        'siteid': 'en',
        'lang': 'en',
        'dont_introduce': [' ('], # , ' in '],
    }
}

accept_all_changes = False
use_config = 'sv'

# ------------------------------------------------------------

siteid = configs[use_config]['siteid']
lang = configs[use_config]['lang']
dont_introduce = configs[use_config]['dont_introduce']
dont_introduce_regexp = re.compile('(?:' + '|'.join(dont_introduce).replace('(', '\(') + ')')

# set up logging to file
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(module)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='update_wd_labels_from_move.log',
                    filemode='a')
log = logging.getLogger()

# define a Handler which writes INFO messages or higher to the sys.stderr
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s %(levelname)-8s %(message)s')
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

# define a Handler which writes WARNING messages or higher to a separate file
warning_handler = logging.FileHandler('update_wd_labels_from_move.warnings.log')
warning_handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(levelname)-8s %(message)s')
warning_handler.setFormatter(formatter)
log.addHandler(warning_handler)

logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('oauthlib').setLevel(logging.WARNING)
logging.getLogger('pywiki').setLevel(logging.WARNING)
logging.getLogger('requests_oauthlib').setLevel(logging.WARNING)
# for key in logging.Logger.manager.loggerDict:
#     print(key)

# --------------------------------------------------------------------------------------------

site = pywikibot.Site(siteid, 'wikipedia')
wdsite = pywikibot.Site('wikidata', 'wikidata')
repo = wdsite.data_repository()


def lcfirst(title):
    if type(title) is list:
        return [lcfirst(x) for x in title]
    if type(title) is set:
        return set([lcfirst(x) for x in title])
    return title[0].lower() + title[1:]


def set_label(item, label, add_alias=True):
    current_label = item.labels.get(lang)
    if current_label == label:
        return

    for di in dont_introduce:
        if di not in current_label and di in label:
            log.warning('%s: Will not change label from "%s" to "%s" since it introduces "%s"',
                        item.id, current_label, label, di)
            return

    if accept_all_changes or yesno('%s: CHANGE "%s" to "%s"?' % (item.id, current_label, label)):
        log.info('%s: CHANGE label from "%s" to "%s"', item.id, current_label, label)

        for di in dont_introduce:
            if di in label:
                log.warning('Label includes "%s" -- please verify manually!' % di)

        item.editLabels({lang: label}, summary='Changing label to reflect page move on %swiki' % siteid)
        if add_alias and current_label not in item.aliases.get(lang, []):
            item.aliases[lang] = item.aliases.get(lang, []) + [current_label]
            item.editAliases(item.aliases, summary='Adding the former label as alias')


# for source in pagegenerators.PreloadingGenerator(gen, groupsize=50):


def logentries_filtered(site, start_at):
    for log_entry in site.logevents(total=500, logtype='move', namespace=0, reverse=True, start=start_at):
        source = log_entry.page()
        target = log_entry.target_page
        ts = log_entry.timestamp().isoformat()

        log.debug('Processing log entry <%s "%s" → "%s">', ts, source.title(), target.title())

        if log_entry.target_ns.id != 0:
            log.info('Page "%s" moved out of article namespace to "%s". Skipping', source.title(), target.title())
            continue

        if not source.exists():
            log.info('Source page no longer exists')
        elif not source.isRedirectPage():
            log.info('Source page "%s" exists, but is not a redirect page! Skipping', source.title())
            continue

        if not target.exists():
            log.info('Target page "%s" does not exist anymore. Skipping', target.title())
            continue
        elif target.isRedirectPage():
            log.info('Target page "%s" is a redirect page! Skipping', target.title())
            continue

        yield log_entry


def get_wikidata_item(page):
    try:
        return page.data_item()
    except NoPage:
        return None


start_at_ts = '2018-01-01T00:00:00'
if os.path.isfile('status.%s.txt' % use_config):
    with open('status.%s.txt' % use_config) as fp:
        start_at_ts = fp.read()


if start_at_ts is not None:
    logging.info('Starting from %s', start_at_ts)


for log_entry in logentries_filtered(site, start_at=start_at_ts):
    ts = log_entry.timestamp().isoformat()

    source = log_entry.page()
    target = log_entry.target_page

    source_item = get_wikidata_item(source)
    item = get_wikidata_item(target)

    source_title = source.title()  # works for non-existing pages too
    target_title = target.title()

    if source_item is not None and item is None:
        log.warning('Sitelink has not been moved from "%s" to "%s"', source_title, target_title)
        continue

    if source_item is not None:
        log.warning('Wikidata item exists for source page "%s"', source_title)
        continue

    if item is None:
        log.info('No wikidata item for "%s"', target_title)
        continue

    # continue

    redirect_titles = set([p.title() for p in target.backlinks(filterRedirects='redirects')])
    redirect_titles = [dont_introduce_regexp.split(x)[0] for x in redirect_titles]

    # The current label at Wikidata
    current_label = item.labels.get(lang)

    if current_label is None:
        log.info('%s: ADD label "%s"', item.id, target_title)
        item.editLabels({lang: target_title}, summary='Add label from %swiki' % siteid)
        for di in dont_introduce:
            if di in target_title:
                log.warning('Label includes "%s" -- please verify manually!' % di)

    elif current_label in redirect_titles:
        # The current Wikidata label matches one of the redirect page title.
        # We will change the Wikidata label to match the current page title.
        set_label(item, target_title)

    elif current_label in lcfirst(redirect_titles):
        # The current Wikidata label matches one of the redirect page title with
        # the first character lowercased. We will change the Wikidata label to match
        # the current page title, preservering the case of the first character.
        set_label(item, lcfirst(target_title))

    elif current_label == source_title:
        # The page was moved without leaving a redirect
        set_label(item, target_title, False)

    elif current_label == lcfirst(source_title):
        # The page was moved without leaving a redirect
        set_label(item, lcfirst(target_title), False)

    elif current_label != target_title and current_label != lcfirst(target_title):
        log.info('Page "%s" moved to "%s". WD label is "%s". Not sure what to do.',
                 source_title, target_title, current_label)

    with open('status.%s.txt' % use_config, 'w+') as fp:
        fp.write(ts)
