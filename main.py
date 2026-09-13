import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import lxml
import time

API_URL = r'https://analyst-assessment-production.up.railway.app'
SESSION = requests.Session()
SESSION.headers.update({
    'Authorization': f'Bearer bh_33nr-Th_3LTQSV3W_0hKhg'
})
PARENT_ID = '0015QAPLGS3FVYEEEM'


def make_decision(message):
    user_input = input(f'{message} (y/n): ')

    while any([user_input.lower()[0] != n for n in ('y', 'n',)]):
        print('\nPlease enter y or n to select\n')
        user_input = input(message)

    return True if user_input.lower()[0] == 'y' else False

def print_account(account, scraped):
    if scraped:
        print(f'\tName: {account["name"]}')
        print(f'\tCity: {account["city"]}')
        print(f'\tCare type: {account["type"]}')
    else:
        print(f'\tId: {account["account_id"]}')
        print(f'\tName: {account["name"]}')
        print(f'\tParent name: {account["parent_name"]}')
        print(f'\tCity: {account["billing_city"]}, {account["billing_state"]}')
        print(f'\tCare type: {account["care_type"]}')
        print(f'\tStatus: {account["status"]}')
        print(f'\tLifetime rev: {account["lifetime_revenue"]}')
        print(f'\tOutstanding ar: {account["outstanding_ar"]}')
        print(f'\tChow: {account["chow_current_account"]}')
        print(f'\tDuplicate account: {account["duplicate_of_account"]}')
        print(f'\tNote: {account["note"]}')

def handle_new_account(account, url, changes):
    decision = make_decision('No CRM account found for this Bellhaven location. Create new account under Bellhaven parent?')
    print('\nNEW')
    print_account(account, True)

    location = account['city'].split(', ')

    if decision:
        aresponse = SESSION.post(url, json={
            'name': account['name'],
            'parent_id': PARENT_ID,
            'billing_city': location[0],
            'billing_state': location[1],
            'care_type': account['type']
        })
        aresponse.raise_for_status()
        print('complete')
        changes += 1
    else:
        print('No changes made')

    return changes

def has_financial_history(account):
    return any([n > 0 for n in (account['lifetime_revenue'], account['outstanding_ar'])])

def choose_winner(matches, url, changes):
    print('Potential duplicate accounts found')

    account_to_match = matches[0]
    resolved_losers = []

    for i, account in enumerate(matches):
        if i == 0: continue

        print('\nACCOUNT 1')
        print_account(account_to_match, False)

        print('\nACCOUNT 2')
        print_account(account, False)

        decision = make_decision('Mark one of these accounts as a duplicate and set to status: Inactive?')
        if decision:
            adecision = make_decision('Mark ACCOUNT 2 as a duplicate of ACCOUNT 1? If no, ACCOUNT 1 will be marked as a duplicate of ACCOUNT 2')
            if adecision:
                aurl = f'{url}/{account["account_id"]}'

                # check for financial history
                if has_financial_history(account):
                    print('\nUpdating CHOW and duplicate status for ACCOUNT 2. Status set to Needs Review.')
                    response = SESSION.patch(aurl, json={
                        'chow_current_account': account_to_match['account_id'],
                        'duplicate_of_account': account_to_match['account_id'],
                        'status': 'Needs Review',
                        'note': 'HB 9/12/26: Duplicate account with financial history'
                    })
                    response.raise_for_status()
                    print('complete')
                    changes += 1

                else:
                    response = SESSION.patch(aurl, json={
                        'duplicate_of_account': account_to_match["account_id"],
                        'status': 'Inactive'
                    })
                    response.raise_for_status()
                    print('complete')
                    changes += 1

                resolved_losers.append(account['account_id'])

                # winning account stays the same
            else:
                aurl = f'{url}/{account_to_match["account_id"]}'

                # check for financial history
                if has_financial_history(account_to_match):
                    print('\nUpdating CHOW and duplicate status for ACCOUNT 1. Status set to Needs Review.')
                    response = SESSION.patch(aurl, json={
                        'chow_current_account': account['account_id'],
                        'duplicate_of_account': account['account_id'],
                        'status': 'Needs Review',
                        'note': 'HB 9/12/26: Duplicate account with financial history'
                    })
                    response.raise_for_status()
                    print('complete')
                    changes += 1
                else:
                    response = SESSION.patch(aurl, json={
                        'duplicate_of_account': account['account_id'],
                        'status': 'Inactive'
                    })
                    response.raise_for_status()
                    print('complete')
                    changes += 1

                resolved_losers.append(account_to_match['account_id'])
                account_to_match = account
        else:
            print('no changes made')

    # return final single winnder
    return account_to_match, resolved_losers, changes


def main():
    #=================#
    ##### SCRAPER #####
    #=================#
    url = f'{API_URL}/communities?page=1'

    data = []
    seen_urls = set()

    while url and url not in seen_urls:
        seen_urls.add(url)

        response = SESSION.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        cards = soup.select('div.card')
        for card in cards:
            h3 = card.find('h3')
            link_tag = h3.find('a') if h3 else None

            if link_tag is None:
                continue

            name = link_tag.get_text(strip=True)
            link_url = urljoin(API_URL, link_tag['href'])

            city_div = card.select_one('div.city')
            city = city_div.get_text(strip=True) if city_div else None
            if city is None or ',' not in city:
                continue

            badge = card.select_one('span.badge')
            community_type = badge.get_text(strip=True) if badge else None
            if community_type is None:
                continue

            data.append({
                'name': name,
                'url': link_url,
                'city': city,
                'type': community_type
            })

        next_link = soup.find('a', string=lambda s: s and 'Next' in s)
        url = urljoin(API_URL, next_link['href']) if next_link else None

        time.sleep(1)

    print(f'Scraped {len(data)} communities total')

    #=================#
    ##### MATCHER #####
    #=================#

    url = f'{API_URL}/api/v1/accounts'

    response = SESSION.get(url, params={'parent_id': PARENT_ID})
    response.raise_for_status()
    bellhaven_parent_accounts = response.json()['data']

    matched_ids = set()
    resolved_ids = set()
    changes_made = 0

    for account in data:
        
        account_location = account['city'].split(', ')

        response = SESSION.get(url, params={'q': 'Bellhaven', 'city': account_location[0], 'state': account_location[1]})
        response.raise_for_status()
        crm_account_data = response.json()['data']

        # store all matches
        matches = [a for a in crm_account_data if a['care_type'] == account['type'] and a['status'].lower() == 'active']

        # no matches, suggest new account
        if len(matches) == 0:
            changes_made = handle_new_account(account, url, changes_made)
            continue

        # if multiple matches, identify duplicates, then regular updates
        if len(matches) > 1:
            crm_account, losers, changes_made = choose_winner(matches, url, changes_made)
            if losers:
                resolved_ids.update(losers)
        elif len(matches) == 1:
            crm_account = matches[0]

        matched_ids.add(crm_account['account_id'])

        # suggest update if name does not match
        if crm_account['name'] != account['name']:
            decision = make_decision('An updated name has been found for this Bellhaven account. Update account name?')
            print('\nCURRENT')
            print_account(crm_account, False)
            print('\nUPDATE')
            print_account(account, True)

            if decision:
                aurl = f'{url}/{crm_account["account_id"]}'
                aresponse = SESSION.patch(aurl, json={'name': account['name']})
                aresponse.raise_for_status()
                print('complete')
                changes_made += 1

        # update parent id (even if name has not been updated Bellhaven should always have the Bellhaven parent account)
        if crm_account['parent_id'] != PARENT_ID:
            # check revenue and outstanding ar
            if any([n > 0 for n in (crm_account['lifetime_revenue'], crm_account['outstanding_ar'])]):
                decision = make_decision('A Bellhaven account with financial history has an incorrect parent_id. Create new account and update chow?')
                print('\nCURRENT')
                print_account(crm_account, False)

                if decision:
                    aresponse = SESSION.post(url, json={
                        'name': account['name'],
                        'parent_id': PARENT_ID,
                        'billing_city': account_location[0],
                        'billing_state': account_location[1],
                        'care_type': account['type']
                    })
                    aresponse.raise_for_status()
                    changes_made += 1

                    new_id = aresponse.json()['data']['account_id']

                    aurl = f'{url}/{crm_account["account_id"]}'
                    aresponse = SESSION.patch(aurl, json={'chow_current_account': new_id})
                    aresponse.raise_for_status()

                    print('complete')
                    changes_made += 1

            else:
                decision = make_decision('A Bellhaven account has an incorrect parent_id. Update account?')
                print('\nCURRENT')
                print_account(crm_account, False)

                if decision:
                    aurl = f'{url}/{crm_account["account_id"]}'
                    aresponse = SESSION.patch(aurl, json={'parent_id': PARENT_ID})
                    aresponse.raise_for_status()
                    print('complete')
                    changes_made += 1

        continue

    orphans = [
        a for a in bellhaven_parent_accounts 
        if a['account_id'] not in matched_ids
        and a['account_id'] not in resolved_ids
        and a['status'].lower() == 'active']
    for orphan in orphans:
        decision = make_decision('Account with Bellhaven parent account no longer found on site. Set status to Needs Review?')
        if decision:
            aurl = f'{url}/{orphan["account_id"]}'
            aresponse = SESSION.patch(aurl, json={'status': 'Needs Review', 'note': 'HB 9/12/26: Location no longer on website'})
            aresponse.raise_for_status()

            print('complete')
            changes_made += 1

    print(f'\n{changes_made} edit{"" if changes_made==1 else "s"} approved and executed.\n')
    print('\nGoodbye\n')

    return 0




if __name__ == '__main__':
    main()
