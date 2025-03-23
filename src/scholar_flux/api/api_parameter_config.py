from typing import  List, Optional, Dict, Any, Union
import requests
import logging
logger = logging.getLogger(__name__)

class APIParameterConfig:

    def __init__(self, query: str, start: str, records_per_page: str, api_key: Optional[str] = None, api_key_required: bool = False,**kwargs):

        self.query: str = query
        self.start: str = start
        self.records_per_page: str = records_per_page
        self.api_key: Optional[str] = api_key or None

        self.parameter_names = dict(query=self.query,
                           start=self.start,
                           records_per_page=self.records_per_page,
                           **kwargs)

        self.additional_parameter_names=dict(**kwargs)

        if api_key or api_key_required:
            api_key_param_name = self.api_key or 'api_key'
            logger.debug("API Key is required: using parameter name, {api_key_param_name}")
            self.parameter_names['api_key']=api_key_param_name

    def _calculate_start_index(self, page: int, records_per_page: int) -> int:
        """Calculates the starting record index for a given page."""
        return 1 + (page - 1) * records_per_page

    #def _dictionary_values(query: str, start: Union[str, int], records_per_page=Union[str,int], api_key= Optional[str],**kwargs):


    def _build_params(self, query: Optional[str], page:int,  records_per_page: Union[str,int], api_key: Optional[str],**kwargs) -> Dict[str, Any]:
        # instanced parameters are generally static: thus page is the only parameter
        # Method to build request parameters
        start = self._calculate_start_index(page,int(records_per_page))

        params={
            self.parameter_names['query']:query,
            self.parameter_names['start']:start,
            self.parameter_names['records_per_page']:records_per_page,

        } | {name:kwargs.get(key,None) for key, name in self.additional_parameter_names.items()}

        if self.parameter_names.get('api_key') is not None:
            key_name=self.parameter_names['api_key']
            params[key_name]=api_key

        return {k: v for k,v in params.items() if v is not None}

    @staticmethod
    def from_defaults(api_name: str,**additional_parameters):
        if api_name == 'springernature':
            return APIParameterConfig(query='q',start='s',records_per_page='p',api_key_required=True,**additional_parameters)
        elif api_name == 'plos':
            return APIParameterConfig(query='q',start='start',records_per_page='rows',api_key=None,api_key_required=False,**additional_parameters)
        else:
            logger.error(f"Default API Config Method: {api_name} not implemented")
            raise NotImplementedError("The requested api default config has not been implemented")
        
    
#   DEFAULT_PARAMS: Dict[str,Any]={
#           'query': 'q',
#           'api_key': 'api_key',
#           'records_per_page': 'p',  # records per page
#           'record_start': 's'  # starting item index
#       }
