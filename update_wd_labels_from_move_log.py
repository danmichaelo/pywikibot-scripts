# Task description:
# https://www.wikidata.org/wiki/Wikidata:Requests_for_permissions/Bot/DanmicholoBot_8

import re
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
    }
}

accept_all_changes = False
use_config = 'sv'

# ------------------------------------------------------------

siteid = configs[use_config]['siteid']
lang = configs[use_config]['lang']
dont_introduce = configs[use_config]['dont_introduce']
dont_introduce_regexp = re.compile('(?:' + '|'.join(dont_introduce).replace('(', '\(') + ')')

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger()

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
            item.editAliases(item.aliases)


gen = pagegenerators.LogeventsPageGenerator(site=site, logtype='move', total='500', namespace=[0])
for source in pagegenerators.PreloadingGenerator(gen, groupsize=50):
    if not source.isRedirectPage():
        continue

    source_title = source.title()
    target = source.getRedirectTarget()
    target_title = target.title()

    redirect_titles = set([p.title() for p in target.backlinks(filterRedirects='redirects')])
    redirect_titles = [dont_introduce_regexp.split(x)[0] for x in redirect_titles]

    try:
        item = target.data_item()
    except NoPage:
        log.warning('No wikidata item for "%s"', target_title)
        continue

    # The current label at Wikidata
    current_label = item.labels.get(lang)

    if current_label is None:
        log.info('%s: ADD label "%s"', item.id, target_title)
        item.editLabels({lang: target_title}, summary='Add label from %swiki' % siteid)

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
