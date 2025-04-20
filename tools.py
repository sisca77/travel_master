"""
여행 관련 도구들을 제공하는 모듈입니다. => 함수들
이 모듈은 항공편 검색, 호텔 검색, 주변 장소 검색, 환율 변환 등의 기능을 제공합니다.
각 도구는 CrewAI의 BaseTool을 상속받아 구현되어 있습니다.

주요 기능:
1. 항공편 검색: Amadeus API를 사용하여 항공편 정보를 검색
2. 호텔 검색: Amadeus API를 사용하여 호텔 정보를 검색
3. 주변 장소 검색: Google Places API를 사용하여 주변 관광지 정보를 검색
4. 환율 변환: Exchange Rate API를 사용하여 통화 변환을 수행
"""

# =============== 필요한 라이브러리 임포트 ===============
import time  # 시간 관련 기능을 위한 라이브러리 (토큰 만료 시간 계산 등에 사용)
from crewai.tools import BaseTool  # CrewAI의 기본 도구 클래스를 상속받기 위한 임포트
from typing import Type, List, Dict  # 타입 힌팅을 위한 임포트 (코드의 타입 안정성을 높임)
from pydantic import BaseModel, Field, PrivateAttr  # 데이터 검증을 위한 Pydantic 임포트
import requests  # HTTP 요청을 위한 라이브러리 (API 호출에 사용)
import os  # 환경 변수 접근을 위한 라이브러리 (API 키 등의 보안 정보 접근에 사용)
from dotenv import load_dotenv  # .env 파일에서 환경 변수를 로드하기 위한 라이브러리

# .env 파일에서 환경 변수를 로드 (API 키 등의 보안 정보를 안전하게 관리)
load_dotenv()

# =============== 항공편 검색 도구 ===============
class FlightSearchInput(BaseModel):
    """
    항공편 검색에 필요한 입력 데이터를 정의하는 클래스
    Pydantic BaseModel을 상속받아 데이터 유효성 검증을 수행
    """
    # 출발 도시명 (한글) - 필수 입력값
    origin_city: str = Field(..., description="출발 도시명(한글), 예: '인천'")
    # 도착 도시명 (한글) - 필수 입력값
    destination_city: str = Field(..., description="도착 도시명(한글), 예: '오사카'")
    # 출발일자 (YYYY-MM-DD 형식) - 필수 입력값
    departure_date: str = Field(..., description="출발일자(YYYY-MM-DD)")
    # 성인 탑승객 수 - 기본값 1
    adults: int = Field(1, description="성인 탑승객 수")


class FlightSearchTool(BaseTool):
    """
    Amadeus API를 사용하여 항공편을 검색하는 도구
    CrewAI의 BaseTool을 상속받아 구현
    """
    # 도구의 기본 정보 설정
    name: str = "항공편 검색 도구"  # 도구의 이름
    description: str = "도시명과 날짜를 입력하면 해당 날짜의 항공편을 조회합니다."  # 도구의 설명
    args_schema: Type[BaseModel] = FlightSearchInput  # 입력 데이터 스키마 정의

    # Amadeus API 토큰을 저장할 private 변수
    # access_token: API 접근 토큰
    # expires_at: 토큰 만료 시간 (초 단위 타임스탬프)
    _amadeus_token: dict = {"access_token": None, "expires_at": 0}

    def get_amadeus_token(self):
        """
        Amadeus API 토큰을 가져오는 메서드
        토큰이 만료되었거나 없는 경우 새로운 토큰을 발급받음
        
        반환값:
            str: Amadeus API 접근 토큰
        """
        # 토큰이 존재하고 만료되지 않았다면 현재 토큰 반환
        if self._amadeus_token["access_token"] and time.time() < self._amadeus_token["expires_at"]:
            return self._amadeus_token["access_token"]

        # 새로운 토큰 발급 요청
        url = "https://test.api.amadeus.com/v1/security/oauth2/token"  # Amadeus API 토큰 발급 엔드포인트
        data = {
            'grant_type': 'client_credentials',  # OAuth2 클라이언트 자격 증명 방식
            'client_id': os.getenv('AMADEUS_CLIENT_ID'),  # 환경 변수에서 클라이언트 ID 가져오기
            'client_secret': os.getenv('AMADEUS_CLIENT_SECRET')  # 환경 변수에서 클라이언트 시크릿 가져오기
        }

        # API 요청 실행
        response = requests.post(url, data=data)
        if response.status_code != 200:
            raise Exception("Amadeus 토큰 발급 실패", response.text)

        # 토큰 정보 저장
        token_data = response.json()
        self._amadeus_token["access_token"] = token_data["access_token"]  # 접근 토큰 저장
        self._amadeus_token["expires_at"] = time.time() + token_data["expires_in"] - 60  # 만료 시간 저장 (60초 여유)

        return self._amadeus_token["access_token"]

    def get_city_code(self, city_name):
        """
        도시명을 IATA 공항 코드로 변환하는 메서드
        지원하지 않는 도시명이 입력된 경우 예외 발생
        
        매개변수:
            city_name (str): 변환할 도시명 (한글)
            
        반환값:
            str: IATA 공항 코드 (예: 'ICN', 'OSA')
            
        예외:
            ValueError: 지원하지 않는 도시명이 입력된 경우
        """
        # 주요 도시들의 IATA 코드 매핑 (한글 도시명 -> IATA 코드)
        city_codes = {
            "서울": "SEL", "부산": "PUS", "제주": "CJU", "대구": "TAE", "인천": "ICN",
            "오사카": "OSA", "도쿄": "TYO", "후쿠오카": "FUK", "삿포로": "SPK", "나고야": "NGO",
            "오키나와": "OKA", "교토": "UKY", "요코하마": "YOK", "히로시마": "HIJ",
            "베이징": "BJS", "상하이": "SHA", "광저우": "CAN", "선전": "SZX", "칭다오": "TAO",
            "홍콩": "HKG", "마카오": "MFM", "시안": "SIA",
            "타이베이": "TPE", "가오슝": "KHH",
            "방콕": "BKK", "푸켓": "HKT", "치앙마이": "CNX",
            "하노이": "HAN", "호치민": "SGN", "다낭": "DAD", "나트랑": "NHA",
            "마닐라": "MNL", "세부": "CEB", "보라카이": "MPH",
            "싱가포르": "SIN",
            "쿠알라룸푸르": "KUL", "코타키나발루": "BKI", "페낭": "PEN",
            "자카르타": "JKT", "발리": "DPS", "족자카르타": "JOG",
            "델리": "DEL", "뭄바이": "BOM", "방갈로르": "BLR"
        }

        # 도시명에 해당하는 IATA 코드 조회
        code = city_codes.get(city_name)
        if not code:
            raise ValueError(f"'{city_name}'의 도시 코드를 찾을 수 없습니다.")
        return code

# run은 이미 규현되이있다 run을 override하면 안된다
# _run을 재정의 사용해야 한다. - 실행함수는 모두 _run 함수로 구현, run은 사용하면 안된다.
    def _run(self, origin_city: str, destination_city: str, departure_date: str, adults: int = 1):
        """
        실제 항공편 검색을 수행하는 메서드
        Amadeus API를 통해 항공편 정보를 조회하고 결과를 반환
        
        매개변수:
            origin_city (str): 출발 도시명 (한글)
            destination_city (str): 도착 도시명 (한글)
            departure_date (str): 출발일자 (YYYY-MM-DD)
            adults (int): 성인 탑승객 수 (기본값: 1)
            
        반환값:
            list: 검색된 항공편 정보 목록
        """
        # 도시명을 IATA 코드로 변환
        origin_code = self.get_city_code(origin_city)
        destination_code = self.get_city_code(destination_city)

        # Amadeus API를 통해 항공편 검색
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"  # 항공편 검색 엔드포인트
        headers = {"Authorization": f"Bearer {self.get_amadeus_token()}"}  # 인증 헤더 설정
        params = {
            "originLocationCode": origin_code,  # 출발지 IATA 코드
            "destinationLocationCode": destination_code,  # 목적지 IATA 코드
            "departureDate": departure_date,  # 출발일자
            "adults": adults,  # 성인 인원 수
            "currencyCode": "KRW",  # 통화 코드 (한국 원화)
            "max": 10  # 최대 검색 결과 수
        }

        # API 요청 실행
        response = requests.get(url, headers=headers, params=params)

        # 응답 상태 확인
        if response.status_code != 200:
            raise Exception("항공편 조회 실패", response.text)

        # 응답 데이터 처리
        flight_data = response.json()
        if "data" not in flight_data or len(flight_data["data"]) == 0:
            return []  # 검색 결과가 없는 경우 빈 리스트 반환

        # 검색된 항공편 정보를 정리하여 반환
        flights = []
        for offer in flight_data["data"]:
            # 각 항공편의 정보를 한글로 정리
            flight_info = {
                "가격": offer["price"]["total"],  # 총 가격
                "통화": offer["price"]["currency"],  # 통화 코드
                "출발지": origin_code,  # 출발지 IATA 코드
                "목적지": destination_code,  # 목적지 IATA 코드
                "출발일": departure_date,  # 출발일자
                "항공사": offer["itineraries"][0]["segments"][0]["carrierCode"],  # 항공사 코드
                "편명": offer["itineraries"][0]["segments"][0]["number"],  # 항공편 번호
                "출발시간": offer["itineraries"][0]["segments"][0]["departure"]["at"],  # 출발 시간
                "도착시간": offer["itineraries"][0]["segments"][-1]["arrival"]["at"]  # 도착 시간
            }
            flights.append(flight_info)

        return flights


# =============== 호텔 검색 도구 ===============
class HotelSearchInput(BaseModel):
    """
    호텔 검색에 필요한 입력 데이터를 정의하는 클래스
    Pydantic BaseModel을 상속받아 데이터 유효성 검증을 수행
    """
    # 숙소를 찾을 도시 이름 (한글) - 필수 입력값
    city_name: str = Field(..., description="숙소를 찾을 도시 이름(예: 오사카, 서울 등)")
    # 체크인 날짜 (YYYY-MM-DD 형식) - 필수 입력값
    check_in_date: str = Field(..., description="체크인 날짜(YYYY-MM-DD)")
    # 체크아웃 날짜 (YYYY-MM-DD 형식) - 필수 입력값
    check_out_date: str = Field(..., description="체크아웃 날짜(YYYY-MM-DD)")
    # 성인 인원 수 - 기본값 1
    adults: int = Field(1, description="성인 인원 수")

class HotelSearchTool(BaseTool):
    """
    Amadeus API를 사용하여 호텔을 검색하는 도구
    CrewAI의 BaseTool을 상속받아 구현
    """
    # 도구의 기본 정보 설정
    name: str = "숙소 검색 도구"  # 도구의 이름
    description: str = "도시 이름과 숙박 일정으로 숙박 가능한 호텔 목록과 가격 정보를 조회합니다."  # 도구의 설명
    args_schema: Type[BaseModel] = HotelSearchInput  # 입력 데이터 스키마 정의

    # Amadeus API 토큰을 저장할 private 변수
    _amadeus_token: Dict[str, any] = PrivateAttr()

    def __init__(self):
        """
        호텔 검색 도구 초기화
        Amadeus API 토큰 변수를 초기화
        """
        super().__init__()  # 부모 클래스 초기화
        self._amadeus_token = {"access_token": None, "expires_at": 0}  # 토큰 변수 초기화

    def get_amadeus_token(self):
        """
        Amadeus API 토큰을 가져오는 메서드
        토큰이 만료되었거나 없는 경우 새로운 토큰을 발급받음
        
        반환값:
            str: Amadeus API 접근 토큰
        """
        # 토큰이 존재하고 만료되지 않았다면 현재 토큰 반환
        if self._amadeus_token["access_token"] and time.time() < self._amadeus_token["expires_at"]:
            return self._amadeus_token["access_token"]

        # 새로운 토큰 발급 요청
        url = "https://test.api.amadeus.com/v1/security/oauth2/token"  # Amadeus API 토큰 발급 엔드포인트
        response = requests.post(url, data={
            'grant_type': 'client_credentials',  # OAuth2 클라이언트 자격 증명 방식
            'client_id': os.getenv('AMADEUS_CLIENT_ID'),  # 환경 변수에서 클라이언트 ID 가져오기
            'client_secret': os.getenv('AMADEUS_CLIENT_SECRET')  # 환경 변수에서 클라이언트 시크릿 가져오기
        })

        # 응답 상태 확인
        if response.status_code != 200:
            raise Exception("Amadeus 토큰 발급 실패", response.text)

        # 토큰 정보 저장
        token_data = response.json()
        self._amadeus_token["access_token"] = token_data["access_token"]  # 접근 토큰 저장
        self._amadeus_token["expires_at"] = time.time() + token_data["expires_in"] - 60  # 만료 시간 저장 (60초 여유)

        return self._amadeus_token["access_token"]

    def get_city_code(self, city_name):
        """
        도시명을 IATA 공항 코드로 변환하는 메서드
        지원하지 않는 도시명이 입력된 경우 예외 발생
        
        매개변수:
            city_name (str): 변환할 도시명 (한글)
            
        반환값:
            str: IATA 공항 코드 (예: 'ICN', 'OSA')
            
        예외:
            ValueError: 지원하지 않는 도시명이 입력된 경우
        """
        # 주요 도시들의 IATA 코드 매핑 (한글 도시명 -> IATA 코드)
        city_codes = {
            "서울": "SEL", "부산": "PUS", "제주": "CJU", "인천": "ICN", "대구": "TAE",
            "오사카": "OSA", "도쿄": "TYO", "후쿠오카": "FUK", "삿포로": "SPK", "교토": "UKY",
            "홍콩": "HKG", "타이베이": "TPE", "방콕": "BKK", "싱가포르": "SIN",
            "하노이": "HAN", "호치민": "SGN", "다낭": "DAD"
        }

        # 도시명에 해당하는 IATA 코드 조회
        code = city_codes.get(city_name)
        if not code:
            raise ValueError(f"'{city_name}'의 도시 코드를 찾을 수 없습니다.")

        return code

    def search_hotels_by_city(self, city_code):
        """
        도시 코드로 호텔 목록을 검색하는 메서드
        Amadeus API를 통해 호텔 정보를 조회
        
        매개변수:
            city_code (str): 도시의 IATA 코드
            
        반환값:
            list: 도시 내 호텔 목록
        """
        url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city"  # 호텔 검색 엔드포인트
        headers = {"Authorization": f"Bearer {self.get_amadeus_token()}"}  # 인증 헤더 설정
        response = requests.get(url, headers=headers, params={"cityCode": city_code})  # API 요청 실행

        # 응답 상태 확인
        if response.status_code != 200:
            return []  # 오류 발생 시 빈 리스트 반환

        return response.json().get("data", [])  # 호텔 목록 반환

    def search_hotel_offers(self, hotel_id, check_in_date, check_out_date, adults=1):
        """
        특정 호텔의 가격 정보를 검색하는 메서드
        Amadeus API를 통해 호텔 가격 정보를 조회
        
        매개변수:
            hotel_id (str): 호텔 ID
            check_in_date (str): 체크인 날짜 (YYYY-MM-DD)
            check_out_date (str): 체크아웃 날짜 (YYYY-MM-DD)
            adults (int): 성인 인원 수 (기본값: 1)
            
        반환값:
            dict: 호텔 가격 정보 또는 None (오류 발생 시)
        """
        url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"  # 호텔 가격 검색 엔드포인트
        headers = {"Authorization": f"Bearer {self.get_amadeus_token()}"}  # 인증 헤더 설정
        response = requests.get(url, headers=headers, params={
            "hotelIds": hotel_id,  # 호텔 ID
            "checkInDate": check_in_date,  # 체크인 날짜
            "checkOutDate": check_out_date,  # 체크아웃 날짜
            "adults": adults  # 성인 인원 수
        })  # API 요청 실행

        # 응답 상태 확인
        if response.status_code != 200:
            return None  # 오류 발생 시 None 반환

        # 응답 데이터 처리
        data = response.json()
        if "data" in data and data["data"]:
            return data["data"][0]  # 첫 번째 호텔 정보 반환
        return None  # 데이터가 없는 경우 None 반환

    def _run(self, city_name: str, check_in_date: str, check_out_date: str, adults: int = 1, max_hotels: int = 10):
        """
        실제 호텔 검색을 수행하는 메서드
        도시의 호텔 목록을 조회하고 각 호텔의 가격 정보를 검색
        
        매개변수:
            city_name (str): 도시명 (한글)
            check_in_date (str): 체크인 날짜 (YYYY-MM-DD)
            check_out_date (str): 체크아웃 날짜 (YYYY-MM-DD)
            adults (int): 성인 인원 수 (기본값: 1)
            max_hotels (int): 최대 검색할 호텔 수 (기본값: 10)
            
        반환값:
            list: 검색된 호텔 정보 목록
        """
        # 도시명을 IATA 코드로 변환
        city_code = self.get_city_code(city_name)
        # 해당 도시의 호텔 목록 검색
        city_hotels = self.search_hotels_by_city(city_code)
        available_hotels = []  # 검색 결과를 저장할 리스트

        # 각 호텔의 가격 정보 검색
        for hotel in city_hotels[:max_hotels]:  # 최대 검색 수 제한
            hotel_offer = self.search_hotel_offers(hotel["hotelId"], check_in_date, check_out_date, adults)
            if hotel_offer:  # 가격 정보가 있는 경우
                # 호텔 정보를 정리하여 저장
                hotel_info = {
                    "hotel_name": hotel_offer["hotel"]["name"],  # 호텔 이름
                    "check_in": check_in_date,  # 체크인 날짜
                    "check_out": check_out_date,  # 체크아웃 날짜
                    "room_description": hotel_offer["offers"][0]["room"]["description"]["text"],  # 객실 설명
                    "total_price": hotel_offer["offers"][0]["price"]["total"],  # 총 가격
                    "currency": hotel_offer["offers"][0]["price"]["currency"]  # 통화 코드
                }
                available_hotels.append(hotel_info)

        return available_hotels  # 검색된 호텔 정보 목록 반환


# =============== 주변 장소 검색 도구 ===============
class NearbyPlacesInput(BaseModel):
    """
    주변 장소 검색에 필요한 입력 데이터를 정의하는 클래스
    Pydantic BaseModel을 상속받아 데이터 유효성 검증을 수행
    """
    # 검색하고자 하는 장소명 - 필수 입력값
    place_name: str = Field(..., description="검색하고자 하는 장소명")
    # 검색 반경 (미터 단위) - 기본값 1000
    radius: int = Field(1000, description="검색 반경(미터 단위)")

class NearbyPlacesTool(BaseTool):
    """
    Google Places API를 사용하여 주변 장소를 검색하는 도구
    CrewAI의 BaseTool을 상속받아 구현
    """
    # 도구의 기본 정보 설정
    name: str = "인근 장소 검색 도구"  # 도구의 이름
    description: str = "특정 장소명으로 인근의 가볼 만한 곳들(관광지, 맛집 등)의 상세 정보를 추천합니다."  # 도구의 설명
    args_schema: Type[BaseModel] = NearbyPlacesInput  # 입력 데이터 스키마 정의

    def _run(self, place_name: str, radius: int = 1000) -> List[dict]:
        """
        실제 주변 장소 검색을 수행하는 메서드
        장소의 좌표를 가져오고 주변 장소들을 검색
        
        매개변수:
            place_name (str): 검색할 장소명
            radius (int): 검색 반경 (미터 단위, 기본값: 1000)
            
        반환값:
            list: 주변 장소 정보 목록
        """
        # 장소의 좌표를 가져옴
        location = self.get_location_by_name(place_name)
        # 주변 장소들을 검색
        nearby_places = self.find_nearby_places(location, radius)
        # 각 장소의 상세 정보를 가져옴
        detailed_places = [self.get_place_details(place["place_id"]) for place in nearby_places]
        return detailed_places  # 상세 정보가 포함된 장소 목록 반환

    def get_location_by_name(self, place_name: str):
        """
        장소명으로 좌표를 검색하는 메서드
        Google Places API를 사용하여 장소의 위도/경도를 조회
        
        매개변수:
            place_name (str): 검색할 장소명
            
        반환값:
            tuple: (위도, 경도)
            
        예외:
            Exception: 장소 검색 실패 시
        """
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"  # 장소 검색 엔드포인트
        params = {
            "query": place_name,  # 검색할 장소명
            "language": "ko",  # 결과 언어 (한국어)
            "key": os.getenv("GOOGLE_API_KEY")  # Google API 키
        }
        response = requests.get(url, params=params).json()  # API 요청 실행

        # 응답 상태 확인
        if response["status"] != "OK":
            raise Exception(f"장소 검색 실패: {response['status']}")

        # 장소의 좌표 반환
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]  # (위도, 경도) 반환

    def find_nearby_places(self, location, radius):
        """
        주변 장소를 검색하는 메서드
        Google Places API를 사용하여 주변 관광지를 검색
        
        매개변수:
            location (tuple): (위도, 경도)
            radius (int): 검색 반경 (미터 단위)
            
        반환값:
            list: 주변 장소 목록
            
        예외:
            Exception: 장소 검색 실패 시
        """
        lat, lng = location  # 위도, 경도 분리
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"  # 주변 장소 검색 엔드포인트
        params = {
            "location": f"{lat},{lng}",  # 검색 중심 좌표
            "radius": radius,  # 검색 반경
            "type": "tourist_attraction",  # 장소 유형 (관광지)
            "language": "ko",  # 결과 언어 (한국어)
            "key": os.getenv("GOOGLE_API_KEY")  # Google API 키
        }
        response = requests.get(url, params=params).json()  # API 요청 실행

        # 응답 상태 확인
        if response["status"] != "OK":
            raise Exception(f"주변 장소 검색 실패: {response['status']}")

        return response["results"][:5]  # 최대 5개의 추천장소 반환

    def get_place_details(self, place_id):
        """
        장소의 상세 정보를 가져오는 메서드
        Google Places API를 사용하여 장소의 상세 정보를 조회
        
        매개변수:
            place_id (str): Google Places 장소 ID
            
        반환값:
            dict: 장소의 상세 정보
            
        예외:
            Exception: 상세 정보 조회 실패 시
        """
        url = "https://maps.googleapis.com/maps/api/place/details/json"  # 장소 상세 정보 엔드포인트
        params = {
            "place_id": place_id,  # 장소 ID
            "language": "ko",  # 결과 언어 (한국어)
            "fields": "name,rating,formatted_address,formatted_phone_number,opening_hours,website,reviews",  # 요청할 필드
            "key": os.getenv("GOOGLE_API_KEY")  # Google API 키
        }
        response = requests.get(url, params=params).json()  # API 요청 실행

        # 응답 상태 확인
        if response["status"] != "OK":
            raise Exception(f"세부 정보 조회 실패: {response['status']}")

        result = response["result"]  # 장소 상세 정보

        # 장소 정보를 한글로 정리하여 반환
        return {
            "이름": result.get("name"),  # 장소 이름
            "주소": result.get("formatted_address"),  # 주소
            "전화번호": result.get("formatted_phone_number", "정보 없음"),  # 전화번호 (없으면 "정보 없음")
            "웹사이트": result.get("website", "정보 없음"),  # 웹사이트 (없으면 "정보 없음")
            "영업시간": result.get("opening_hours", {}).get("weekday_text", "정보 없음"),  # 영업시간 (없으면 "정보 없음")
            "평점": result.get("rating", "정보 없음"),  # 평점 (없으면 "정보 없음")
            "리뷰": [{  # 리뷰 목록 (최대 3개)
                "내용": review.get("text"),  # 리뷰 내용
                "평점": review.get("rating")  # 리뷰 평점
            } for review in result.get("reviews", [])[:3]]  # 최대 3개 리뷰
        }


# =============== 환율 변환 도구 ===============
class ExchangeRateInput(BaseModel):
    """
    환율 변환에 필요한 입력 데이터를 정의하는 클래스
    Pydantic BaseModel을 상속받아 데이터 유효성 검증을 수행
    """
    # 원본 통화의 코드 - 필수 입력값
    from_currency: str = Field(..., description="원본 통화의 코드 (예: USD)")
    # 변환할 대상 통화의 코드 - 필수 입력값
    to_currency: str = Field(..., description="변환할 대상 통화의 코드 (예: KRW)")
    # 변환할 금액 - 필수 입력값
    amount: float = Field(..., description="변환할 금액")

class ExchangeRateTool(BaseTool):
    """
    Exchange Rate API를 사용하여 환율 변환을 수행하는 도구
    CrewAI의 BaseTool을 상속받아 구현
    """
    # 도구의 기본 정보 설정
    name: str = "환율 도구"  # 도구의 이름
    description: str = "특정 금액을 한 통화에서 다른 통화로 변환하는 툴입니다."  # 도구의 설명
    args_schema: type[BaseModel] = ExchangeRateInput  # 입력 데이터 스키마 정의

    def _run(self, from_currency: str, to_currency: str, amount: float):
        """
        실제 환율 변환을 수행하는 메서드
        Exchange Rate API를 사용하여 통화 변환을 수행
        
        매개변수:
            from_currency (str): 원본 통화 코드 (예: USD)
            to_currency (str): 대상 통화 코드 (예: KRW)
            amount (float): 변환할 금액
            
        반환값:
            dict: 변환 결과 정보
            
        예외:
            Exception: 환율 정보 조회 실패 시
        """
        api_key = os.getenv('EXCHANGE_RATE_API_KEY')  # 환경 변수에서 API 키 가져오기
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_currency}/{to_currency}/{amount}"  # 환율 변환 엔드포인트

        # API 요청 실행
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("환율 정보 조회 실패", response.text)

        # 응답 데이터 처리
        data = response.json()

        # 응답 상태 확인
        if data['result'] != "success":
            raise Exception("환율 조회에 실패했습니다", data.get('error-type', 'unknown error'))

        converted_amount = data['conversion_result']  # 변환된 금액

        # 변환 결과 정보 반환
        return {
            "from_currency": from_currency,  # 원본 통화
            "to_currency": to_currency,  # 대상 통화
            "original_amount": amount,  # 원본 금액
            "converted_amount": converted_amount,  # 변환된 금액
            "conversion_rate": data["conversion_rate"]  # 변환 환율
        }
        
        