import framework
# unique to module
import pwnedlist
import os

class Module(framework.module):

    def __init__(self, params):
        framework.module.__init__(self, params)
        self.register_option('source', 'db', 'yes', 'source of accounts for module input (see \'info\' for options)')
        self.info = {
                     'Name': 'PwnedList - Account Credentials Fetcher',
                     'Author': 'Tim Tomes (@LaNMaSteR53)',
                     'Description': 'Queries the PwnedList API for credentials associated with the given usernames and updates the \'creds\' table of the database with the results.',
                     'Comments': [
                                  'Source options: [ db | email.address@domain.com | ./path/to/file | query <sql> ]',
                                  'API Query Cost: 1 query per request.'
                                  ]
                     }

    def module_run(self):
        # api key management
        key = self.manage_key('pwned_key', 'PwnedList API Key')
        if not key: return
        secret = self.manage_key('pwned_secret', 'PwnedList API Secret')
        if not secret: return
        decrypt_key = secret[:16]
        iv = self.manage_key('pwned_iv', 'PwnedList Decryption IV')
        if not iv: return

        accounts = self.get_source(self.options['source']['value'], 'SELECT DISTINCT username FROM creds WHERE username IS NOT NULL and password IS NULL ORDER BY username')
        if not accounts: return

        # API query guard
        if not self.api_guard(1): return

        # setup API call
        method = 'accounts.query'
        url = 'https://pwnedlist.com/api/1/%s' % (method.replace('.','/'))

        # build the payload
        payload = {'account_identifier': ','.join(accounts), 'daysAgo': 0}
        payload = pwnedlist.build_payload(payload, method, key, secret)
        # make request
        try: resp = self.request(url, payload=payload)
        except KeyboardInterrupt:
            print ''
            return
        except Exception as e:
            self.error(e.__str__())
            return
        if resp.json: jsonobj = resp.json
        else:
            self.error('Invalid JSON response.\n%s' % (resp.text))
            return
        if len(jsonobj['results']) == 0:
            self.output('No results returned')
        else:
            cnt = 0
            new = 0
            for cred in jsonobj['results']:
                username = cred['plain']
                password = pwnedlist.decrypt(cred['password'], decrypt_key, iv)
                password = "".join([i for i in password if ord(i) in range(32, 126)])
                leak = cred['leak_id']
                self.output('%s:%s' % (username, password))
                cnt += 1
                new += self.add_cred(username, password, None, leak)
                self.query("DELETE FROM creds WHERE username = '%s' and password IS NULL and hash IS NULL" % (username))
            self.output('%d total credentials found.' % (cnt))
            if new: self.alert('%d NEW credentials found!' % (new))
