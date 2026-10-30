from fastapi import HTTPException


def require_catalog_id(catalog,class_id):
    if type(class_id) is not int or class_id not in catalog.by_id:
        raise HTTPException(422,'Unknown sign catalog ID')
    return catalog.by_id[class_id]
