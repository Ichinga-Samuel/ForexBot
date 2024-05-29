from copy import deepcopy, copy
from dataclasses import dataclass, asdict, fields


@dataclass
class Male:
    man: str
    boy: str
    dr: dict
    girl: int = 4

    @property
    def data(self) -> dict:
        # k = self.__dict__.keys
        data = {}
        for k in self.__dict__.keys():
            data[k] = getattr(self, k)
        return self.__dict__

drr = {}
m = Male(man='man', boy='boy', dr=drr)
print(m.dr)
drr['gender'] = ''
cp = deepcopy(m.data)
print(cp)
# print((m.data|{'girl': 4}))
