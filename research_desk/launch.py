"""Local first-run launcher. Generated credentials live only for this server run."""
import json,os,secrets
from server import main
if __name__=='__main__':
    if 'BETTING_USERS' not in os.environ:
        token=secrets.token_urlsafe(32)
        os.environ['BETTING_USERS']=json.dumps({'local':token})
        print('Local dashboard token (enter in the browser; changes on next launch):',token,flush=True)
    main()
